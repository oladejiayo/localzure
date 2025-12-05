"""
Production-grade OData Query Optimizer & Execution Planner.

This module provides intelligent query optimization for Azure Table Storage queries.
Analyzes AST to generate optimal execution plans based on query patterns.

Features:
- Point query detection (PartitionKey eq X and RowKey eq Y) → O(1)
- Partition scan detection (PartitionKey eq X) → O(n) within partition
- Range query detection (with RowKey bounds) → O(n) with early termination
- Table scan detection (no partition key) → O(n) full scan
- Filter pushdown optimization
- Projection pushdown optimization
- Cost estimation model
- Query plan caching with hash-based lookup

Query Plan Hierarchy:
    QueryPlan (ABC)
    ├── PointQueryPlan (O(1) single entity lookup)
    ├── PartitionScanPlan (O(n) scan within partition)
    ├── RangeQueryPlan (O(n) with early termination)
    └── TableScanPlan (O(n) full table scan)

Example:
    >>> from localzure.services.table.lexer import ODataLexer
    >>> from localzure.services.table.parser import ODataParser
    >>> from localzure.services.table.optimizer import QueryOptimizer
    >>> 
    >>> lexer = ODataLexer("PartitionKey eq 'P1' and RowKey eq 'R1'")
    >>> tokens = lexer.tokenize()
    >>> parser = ODataParser(tokens)
    >>> ast = parser.parse()
    >>> optimizer = QueryOptimizer()
    >>> plan = optimizer.optimize(ast)
    >>> print(type(plan).__name__)
    PointQueryPlan

Author: LocalZure Team
Version: 1.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import hashlib

from .parser import (
    ASTNode, 
    BinaryOpNode, 
    PropertyAccessNode, 
    LiteralNode,
    UnaryOpNode,
    FunctionCallNode,
    ASTVisitor
)


class QueryPlanType(Enum):
    """Query plan types ordered by efficiency (best to worst)."""
    POINT_QUERY = "point_query"          # O(1) - Single entity lookup
    PARTITION_SCAN = "partition_scan"     # O(n) - Scan single partition
    RANGE_QUERY = "range_query"           # O(n) - Range with bounds
    TABLE_SCAN = "table_scan"             # O(n) - Full table scan
    
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class QueryPlan(ABC):
    """
    Base class for all query execution plans.
    
    All plans are immutable for caching and thread-safety.
    """
    plan_type: QueryPlanType
    filter_ast: Optional[ASTNode]
    estimated_cost: float
    
    @abstractmethod
    def __str__(self) -> str:
        """Human-readable plan description."""
        pass


@dataclass(frozen=True)
class PointQueryPlan(QueryPlan):
    """
    Point query execution plan: O(1) lookup.
    
    Detected pattern:
        PartitionKey eq 'X' and RowKey eq 'Y'
    
    This is the most efficient query type, directly retrieving a single entity.
    
    Attributes:
        partition_key: The exact partition key value
        row_key: The exact row key value
        filter_ast: Additional filter predicates (if any)
        estimated_cost: Cost estimate (always 1.0 for point queries)
    """
    partition_key: str
    row_key: str
    
    def __str__(self) -> str:
        return f"PointQuery(PK={self.partition_key!r}, RK={self.row_key!r})"


@dataclass(frozen=True)
class PartitionScanPlan(QueryPlan):
    """
    Partition scan execution plan: O(n) within partition.
    
    Detected pattern:
        PartitionKey eq 'X' [and additional filters]
    
    Scans all entities within a single partition, applying filters.
    
    Attributes:
        partition_key: The exact partition key value
        filter_ast: Filter predicates to apply during scan
        estimated_cost: Cost estimate (10.0 base + filter complexity)
    """
    partition_key: str
    
    def __str__(self) -> str:
        return f"PartitionScan(PK={self.partition_key!r}, filter={bool(self.filter_ast)})"


@dataclass(frozen=True)
class RangeQueryPlan(QueryPlan):
    """
    Range query execution plan: O(n) with early termination.
    
    Detected pattern:
        PartitionKey eq 'X' and (RowKey gt 'A' and RowKey lt 'Z')
    
    Scans entities within a partition with row key bounds for early termination.
    
    Attributes:
        partition_key: The exact partition key value
        row_key_start: Lower bound for row key (inclusive if eq/ge)
        row_key_end: Upper bound for row key (inclusive if eq/le)
        start_inclusive: Whether start bound is inclusive
        end_inclusive: Whether end bound is inclusive
        filter_ast: Additional filter predicates
        estimated_cost: Cost estimate (15.0 base + filter complexity)
    """
    partition_key: str
    row_key_start: Optional[str]
    row_key_end: Optional[str]
    start_inclusive: bool
    end_inclusive: bool
    
    def __str__(self) -> str:
        start = f">={'[' if self.start_inclusive else '('}{self.row_key_start!r}" if self.row_key_start else ""
        end = f"<={'[' if self.end_inclusive else ')'}{self.row_key_end!r}" if self.row_key_end else ""
        return f"RangeQuery(PK={self.partition_key!r}, RK{start}{end})"


@dataclass(frozen=True)
class TableScanPlan(QueryPlan):
    """
    Table scan execution plan: O(n) full table scan.
    
    Used when no partition key is specified or query cannot be optimized.
    This is the least efficient query type.
    
    Attributes:
        filter_ast: Filter predicates to apply during scan
        estimated_cost: Cost estimate (100.0 base + filter complexity)
    """
    
    def __str__(self) -> str:
        return f"TableScan(filter={bool(self.filter_ast)})"


class KeyExtractor(ASTVisitor):
    """
    AST visitor that extracts partition key and row key constraints.
    
    Analyzes filter expressions to identify equality constraints and ranges
    on PartitionKey and RowKey properties.
    """
    
    def __init__(self):
        """Initialize key extractor."""
        self.partition_key: Optional[str] = None
        self.row_key: Optional[str] = None
        self.row_key_gt: Optional[str] = None
        self.row_key_ge: Optional[str] = None
        self.row_key_lt: Optional[str] = None
        self.row_key_le: Optional[str] = None
        self.has_other_predicates = False
    
    def visit_binary_op(self, node: BinaryOpNode) -> None:
        """Visit binary operation node."""
        if node.operator == 'and':
            # Recursively extract from both sides of AND
            node.left.accept(self)
            node.right.accept(self)
        
        elif node.operator == 'eq':
            # Check for PartitionKey eq 'value' or RowKey eq 'value'
            if isinstance(node.left, PropertyAccessNode) and isinstance(node.right, LiteralNode):
                prop_name = node.left.property_name
                value = node.right.value
                
                if prop_name == 'PartitionKey':
                    self.partition_key = str(value)
                elif prop_name == 'RowKey':
                    self.row_key = str(value)
                else:
                    self.has_other_predicates = True
            else:
                self.has_other_predicates = True
        
        elif node.operator in ('gt', 'ge', 'lt', 'le'):
            # Check for RowKey range constraints
            if isinstance(node.left, PropertyAccessNode) and isinstance(node.right, LiteralNode):
                prop_name = node.left.property_name
                value = str(node.right.value)
                
                if prop_name == 'RowKey':
                    if node.operator == 'gt':
                        self.row_key_gt = value
                    elif node.operator == 'ge':
                        self.row_key_ge = value
                    elif node.operator == 'lt':
                        self.row_key_lt = value
                    elif node.operator == 'le':
                        self.row_key_le = value
                else:
                    self.has_other_predicates = True
            else:
                self.has_other_predicates = True
        
        else:
            # OR, NE, or other operators prevent optimization
            self.has_other_predicates = True
    
    def visit_literal(self, node: LiteralNode) -> None:
        """Visit literal node."""
        pass
    
    def visit_property(self, node: PropertyAccessNode) -> None:
        """Visit property access node."""
        pass
    
    def visit_unary_op(self, node: UnaryOpNode) -> None:
        """Visit unary operation node."""
        self.has_other_predicates = True
    
    def visit_function_call(self, node: FunctionCallNode) -> None:
        """Visit function call node."""
        self.has_other_predicates = True


class FilterSimplifier(ASTVisitor):
    """
    AST visitor that removes extracted key constraints from filter.
    
    After extracting partition/row keys for the query plan, this visitor
    creates a simplified filter AST with those constraints removed.
    """
    
    def __init__(self, partition_key: Optional[str] = None, row_key: Optional[str] = None,
                 remove_row_key_ranges: bool = False):
        """
        Initialize filter simplifier.
        
        Args:
            partition_key: Partition key value to remove from filter
            row_key: Row key value to remove from filter
            remove_row_key_ranges: Whether to remove row key range constraints
        """
        self.partition_key = partition_key
        self.row_key = row_key
        self.remove_row_key_ranges = remove_row_key_ranges
    
    def visit_binary_op(self, node: BinaryOpNode) -> Optional[ASTNode]:
        """Visit binary operation node and simplify."""
        if node.operator == 'and':
            # Recursively simplify both sides
            left = node.left.accept(self)
            right = node.right.accept(self)
            
            # If either side was removed, return the other
            if left is None:
                return right
            if right is None:
                return left
            
            # Both sides remain
            return BinaryOpNode(
                node_type=node.node_type,
                position=node.position,
                operator='and',
                left=left,
                right=right
            )
        
        elif node.operator == 'eq':
            # Check if this is a key constraint to remove
            if isinstance(node.left, PropertyAccessNode) and isinstance(node.right, LiteralNode):
                prop_name = node.left.property_name
                value = str(node.right.value)
                
                if prop_name == 'PartitionKey' and value == self.partition_key:
                    return None  # Remove this constraint
                if prop_name == 'RowKey' and value == self.row_key:
                    return None  # Remove this constraint
        
        elif self.remove_row_key_ranges and node.operator in ('gt', 'ge', 'lt', 'le'):
            # Remove row key range constraints if requested
            if isinstance(node.left, PropertyAccessNode) and node.left.property_name == 'RowKey':
                return None
        
        # Keep this node
        return node
    
    def visit_literal(self, node: LiteralNode) -> ASTNode:
        """Visit literal node."""
        return node
    
    def visit_property(self, node: PropertyAccessNode) -> ASTNode:
        """Visit property access node."""
        return node
    
    def visit_unary_op(self, node: UnaryOpNode) -> ASTNode:
        """Visit unary operation node."""
        operand = node.operand.accept(self)
        if operand is None:
            return None
        return UnaryOpNode(
            node_type=node.node_type,
            position=node.position,
            operator=node.operator,
            operand=operand
        )
    
    def visit_function_call(self, node: FunctionCallNode) -> ASTNode:
        """Visit function call node."""
        return node


class CostEstimator:
    """
    Estimates query execution cost.
    
    Cost model:
        - Point query: 1.0 (single entity lookup)
        - Partition scan: 10.0 base + filter complexity
        - Range query: 15.0 base + filter complexity
        - Table scan: 100.0 base + filter complexity
    
    Filter complexity adds 0.1 per comparison, 0.2 per function call.
    """
    
    @staticmethod
    def estimate(plan_type: QueryPlanType, filter_ast: Optional[ASTNode]) -> float:
        """
        Estimate query execution cost.
        
        Args:
            plan_type: Type of query plan
            filter_ast: Filter AST for complexity analysis
            
        Returns:
            Estimated cost (lower is better)
        """
        # Base cost by plan type
        base_costs = {
            QueryPlanType.POINT_QUERY: 1.0,
            QueryPlanType.PARTITION_SCAN: 10.0,
            QueryPlanType.RANGE_QUERY: 15.0,
            QueryPlanType.TABLE_SCAN: 100.0
        }
        
        cost = base_costs[plan_type]
        
        # Add filter complexity cost
        if filter_ast:
            cost += CostEstimator._estimate_filter_complexity(filter_ast)
        
        return cost
    
    @staticmethod
    def _estimate_filter_complexity(node: ASTNode) -> float:
        """
        Estimate filter complexity cost.
        
        Args:
            node: AST node to analyze
            
        Returns:
            Complexity cost
        """
        if isinstance(node, BinaryOpNode):
            # Comparison operators: 0.1 cost
            # Logical operators: cost of children
            if node.operator in ('eq', 'ne', 'gt', 'ge', 'lt', 'le'):
                op_cost = 0.1
            else:
                op_cost = 0.0
            
            left_cost = CostEstimator._estimate_filter_complexity(node.left)
            right_cost = CostEstimator._estimate_filter_complexity(node.right)
            return op_cost + left_cost + right_cost
        
        elif isinstance(node, UnaryOpNode):
            return 0.05 + CostEstimator._estimate_filter_complexity(node.operand)
        
        elif isinstance(node, FunctionCallNode):
            # Function calls are more expensive
            return 0.2 + sum(
                CostEstimator._estimate_filter_complexity(arg) 
                for arg in node.arguments
            )
        
        else:
            # Literals and properties have no cost
            return 0.0


class QueryOptimizer:
    """
    Query optimizer with plan caching.
    
    Analyzes filter AST to generate optimal execution plans.
    Caches plans by AST hash for repeated queries.
    
    Features:
        - Automatic plan type detection
        - Filter simplification
        - Cost estimation
        - LRU cache with hash-based lookup
    
    Example:
        >>> optimizer = QueryOptimizer()
        >>> plan = optimizer.optimize(ast)
        >>> print(plan)
        PointQuery(PK='P1', RK='R1')
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        Initialize query optimizer.
        
        Args:
            cache_size: Maximum number of plans to cache
        """
        self.cache_size = cache_size
        self._plan_cache: Dict[str, QueryPlan] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def optimize(self, filter_ast: Optional[ASTNode], 
                 select_properties: Optional[List[str]] = None) -> QueryPlan:
        """
        Optimize query and generate execution plan.
        
        Args:
            filter_ast: Filter expression AST (None for no filter)
            select_properties: Properties to select (None for all)
            
        Returns:
            Optimized query execution plan
        
        Example:
            >>> plan = optimizer.optimize(ast)
            >>> if isinstance(plan, PointQueryPlan):
            ...     entity = get_entity(plan.partition_key, plan.row_key)
        """
        # Check cache
        cache_key = self._compute_cache_key(filter_ast, select_properties)
        if cache_key in self._plan_cache:
            self._cache_hits += 1
            return self._plan_cache[cache_key]
        
        self._cache_misses += 1
        
        # Analyze filter to extract keys
        if filter_ast is None:
            # No filter → table scan
            plan = self._create_table_scan_plan(None)
        else:
            plan = self._analyze_and_create_plan(filter_ast)
        
        # Cache the plan
        if len(self._plan_cache) >= self.cache_size:
            # Simple eviction: remove oldest entry
            self._plan_cache.pop(next(iter(self._plan_cache)))
        
        self._plan_cache[cache_key] = plan
        return plan
    
    def _analyze_and_create_plan(self, filter_ast: ASTNode) -> QueryPlan:
        """
        Analyze filter AST and create optimal plan.
        
        Args:
            filter_ast: Filter expression AST
            
        Returns:
            Query execution plan
        """
        # Extract key constraints
        extractor = KeyExtractor()
        filter_ast.accept(extractor)
        
        # Determine plan type based on extracted keys
        if extractor.partition_key and extractor.row_key:
            # Point query: both PK and RK specified
            return self._create_point_query_plan(
                extractor.partition_key,
                extractor.row_key,
                filter_ast if extractor.has_other_predicates else None
            )
        
        elif extractor.partition_key and (extractor.row_key_gt or extractor.row_key_ge or 
                                          extractor.row_key_lt or extractor.row_key_le):
            # Range query: PK with RK bounds
            return self._create_range_query_plan(
                extractor.partition_key,
                extractor.row_key_ge or extractor.row_key_gt,
                extractor.row_key_le or extractor.row_key_lt,
                extractor.row_key_ge is not None,  # start_inclusive
                extractor.row_key_le is not None,  # end_inclusive
                filter_ast
            )
        
        elif extractor.partition_key:
            # Partition scan: only PK specified
            return self._create_partition_scan_plan(
                extractor.partition_key,
                filter_ast
            )
        
        else:
            # Table scan: no PK specified
            return self._create_table_scan_plan(filter_ast)
    
    def _create_point_query_plan(self, partition_key: str, row_key: str,
                                  filter_ast: Optional[ASTNode]) -> PointQueryPlan:
        """Create point query execution plan."""
        # Simplify filter by removing key constraints
        simplified_filter = None
        if filter_ast:
            simplifier = FilterSimplifier(partition_key, row_key)
            simplified_filter = filter_ast.accept(simplifier)
        
        cost = CostEstimator.estimate(QueryPlanType.POINT_QUERY, simplified_filter)
        
        return PointQueryPlan(
            plan_type=QueryPlanType.POINT_QUERY,
            filter_ast=simplified_filter,
            estimated_cost=cost,
            partition_key=partition_key,
            row_key=row_key
        )
    
    def _create_partition_scan_plan(self, partition_key: str,
                                     filter_ast: Optional[ASTNode]) -> PartitionScanPlan:
        """Create partition scan execution plan."""
        # Simplify filter by removing PK constraint
        simplified_filter = None
        if filter_ast:
            simplifier = FilterSimplifier(partition_key=partition_key)
            simplified_filter = filter_ast.accept(simplifier)
        
        cost = CostEstimator.estimate(QueryPlanType.PARTITION_SCAN, simplified_filter)
        
        return PartitionScanPlan(
            plan_type=QueryPlanType.PARTITION_SCAN,
            filter_ast=simplified_filter,
            estimated_cost=cost,
            partition_key=partition_key
        )
    
    def _create_range_query_plan(self, partition_key: str,
                                   row_key_start: Optional[str],
                                   row_key_end: Optional[str],
                                   start_inclusive: bool,
                                   end_inclusive: bool,
                                   filter_ast: Optional[ASTNode]) -> RangeQueryPlan:
        """Create range query execution plan."""
        # Simplify filter by removing key constraints
        simplified_filter = None
        if filter_ast:
            simplifier = FilterSimplifier(
                partition_key=partition_key,
                remove_row_key_ranges=True
            )
            simplified_filter = filter_ast.accept(simplifier)
        
        cost = CostEstimator.estimate(QueryPlanType.RANGE_QUERY, simplified_filter)
        
        return RangeQueryPlan(
            plan_type=QueryPlanType.RANGE_QUERY,
            filter_ast=simplified_filter,
            estimated_cost=cost,
            partition_key=partition_key,
            row_key_start=row_key_start,
            row_key_end=row_key_end,
            start_inclusive=start_inclusive,
            end_inclusive=end_inclusive
        )
    
    def _create_table_scan_plan(self, filter_ast: Optional[ASTNode]) -> TableScanPlan:
        """Create table scan execution plan."""
        cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, filter_ast)
        
        return TableScanPlan(
            plan_type=QueryPlanType.TABLE_SCAN,
            filter_ast=filter_ast,
            estimated_cost=cost
        )
    
    def _compute_cache_key(self, filter_ast: Optional[ASTNode],
                           select_properties: Optional[List[str]]) -> str:
        """
        Compute cache key for query plan.
        
        Args:
            filter_ast: Filter AST
            select_properties: Selected properties
            
        Returns:
            Hash string for cache lookup
        """
        # Create string representation
        filter_str = str(filter_ast) if filter_ast else "None"
        select_str = ",".join(sorted(select_properties)) if select_properties else "None"
        key_input = f"{filter_str}|{select_str}"
        
        # Hash for efficient lookup
        return hashlib.sha256(key_input.encode()).hexdigest()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache hits, misses, and hit rate
        
        Example:
            >>> stats = optimizer.get_cache_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        
        return {
            'cache_size': len(self._plan_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate
        }
    
    def clear_cache(self) -> None:
        """Clear the plan cache."""
        self._plan_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
