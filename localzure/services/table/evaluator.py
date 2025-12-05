"""
Production-grade OData Query Evaluator & Execution Engine.

This module provides a high-performance AST evaluator using the visitor pattern
with lazy evaluation, null safety, and type coercion for Azure Table Storage queries.

Features:
- Visitor-based AST traversal
- Lazy evaluation with short-circuit logic
- Null-safe property access (three-valued logic)
- Automatic type coercion and numeric promotion
- Efficient entity filtering (stream-based)
- Projection support (select specific properties)
- Pagination with continuation tokens
- Configurable query timeout

Example:
    >>> from localzure.services.table.lexer import ODataLexer
    >>> from localzure.services.table.parser import ODataParser
    >>> from localzure.services.table.evaluator import QueryEvaluator
    >>> 
    >>> lexer = ODataLexer("Price gt 50 and Active eq true")
    >>> tokens = lexer.tokenize()
    >>> parser = ODataParser(tokens)
    >>> ast = parser.parse()
    >>> 
    >>> evaluator = QueryEvaluator()
    >>> entity = {'Price': 75.0, 'Active': True}
    >>> result = evaluator.evaluate(ast, entity)
    >>> print(result)  # True

Author: LocalZure Team
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import time

from .parser import (
    ASTNode,
    ASTVisitor,
    BinaryOpNode,
    UnaryOpNode,
    LiteralNode,
    PropertyAccessNode,
    FunctionCallNode,
)
from .types import EdmType, TypedValue, TypeValidator
from .functions import FunctionRegistry


class EvaluationError(Exception):
    """
    Query evaluation error.
    
    Raised when runtime evaluation fails, such as division by zero,
    type mismatches, or function call errors.
    """
    
    def __init__(self, message: str, node: Optional[ASTNode] = None):
        super().__init__(message)
        self.node = node
        self.message = message


class TimeoutError(EvaluationError):
    """
    Query execution timeout.
    
    Raised when query execution exceeds configured timeout limit.
    """
    
    def __init__(self, elapsed_ms: float, timeout_ms: float):
        super().__init__(
            f"Query execution timeout: {elapsed_ms:.1f}ms exceeded limit of {timeout_ms:.0f}ms"
        )
        self.elapsed_ms = elapsed_ms
        self.timeout_ms = timeout_ms


class FilterEvaluator(ASTVisitor):
    """
    AST visitor that evaluates filter expressions against entities.
    
    Implements three-valued logic for null handling:
    - True: condition satisfied
    - False: condition not satisfied
    - None: condition cannot be determined (null operand)
    
    Features:
        - Lazy evaluation (short-circuit AND/OR)
        - Null-safe property access
        - Automatic type coercion
        - Function call execution
    
    Thread Safety:
        FilterEvaluator instances are NOT thread-safe. Create separate
        instances for concurrent evaluation.
    """
    
    def __init__(
        self,
        entity: Dict[str, Any],
        type_validator: Optional[TypeValidator] = None,
        function_registry: Optional[FunctionRegistry] = None,
        case_sensitive_props: bool = False
    ):
        """
        Initialize filter evaluator.
        
        Args:
            entity: Entity to evaluate against
            type_validator: Type validator for type checking
            function_registry: Function registry for function calls
            case_sensitive_props: Whether property names are case-sensitive
        """
        self.entity = entity
        self.type_validator = type_validator or TypeValidator()
        self.function_registry = function_registry or FunctionRegistry()
        self.case_sensitive_props = case_sensitive_props
    
    def visit_literal(self, node: LiteralNode) -> Any:
        """
        Visit literal node.
        
        Returns:
            Literal value
        """
        return node.value
    
    def visit_property(self, node: PropertyAccessNode) -> Any:
        """
        Visit property access node with null-safe access.
        
        Args:
            node: Property access node
            
        Returns:
            Property value, or None if property doesn't exist
        """
        prop_name = node.property_name
        
        # Case-insensitive property lookup if configured
        if not self.case_sensitive_props:
            # Try exact match first
            if prop_name in self.entity:
                return self.entity[prop_name]
            
            # Try case-insensitive match
            for key in self.entity:
                if key.lower() == prop_name.lower():
                    return self.entity[key]
            
            # Property not found
            return None
        else:
            # Case-sensitive lookup
            return self.entity.get(prop_name, None)
    
    def visit_unary_op(self, node: UnaryOpNode) -> Any:
        """
        Visit unary operation node.
        
        Supports:
        - not: logical negation (three-valued logic)
        - -: numeric negation
        
        Args:
            node: Unary operation node
            
        Returns:
            Result of operation, or None if operand is null
        """
        operand = node.operand.accept(self)
        
        if node.operator == 'not':
            # Three-valued logic for NOT
            if operand is None:
                return None
            return not operand
        
        elif node.operator == '-':
            # Numeric negation
            if operand is None:
                return None
            return -operand
        
        else:
            raise EvaluationError(f"Unknown unary operator: {node.operator}", node)
    
    def visit_binary_op(self, node: BinaryOpNode) -> Any:
        """
        Visit binary operation node with lazy evaluation.
        
        Supports:
        - Logical: and, or
        - Comparison: eq, ne, gt, ge, lt, le
        - Arithmetic: add, sub, mul, div, mod
        
        Args:
            node: Binary operation node
            
        Returns:
            Result of operation
        """
        operator = node.operator
        
        # Lazy evaluation for logical operators
        if operator == 'and':
            return self._eval_and(node)
        elif operator == 'or':
            return self._eval_or(node)
        
        # Eager evaluation for other operators
        left = node.left.accept(self)
        right = node.right.accept(self)
        
        # Null propagation for comparison and arithmetic
        if left is None or right is None:
            # Null comparisons
            if operator == 'eq':
                return left is None and right is None
            elif operator == 'ne':
                return not (left is None and right is None)
            else:
                # Other operators: null propagates
                return None
        
        # Comparison operators
        if operator == 'eq':
            return self._compare_eq(left, right)
        elif operator == 'ne':
            return self._compare_ne(left, right)
        elif operator == 'gt':
            return self._compare_gt(left, right)
        elif operator == 'ge':
            return self._compare_ge(left, right)
        elif operator == 'lt':
            return self._compare_lt(left, right)
        elif operator == 'le':
            return self._compare_le(left, right)
        
        # Arithmetic operators
        elif operator == 'add':
            return left + right
        elif operator == 'sub':
            return left - right
        elif operator == 'mul':
            return left * right
        elif operator == 'div':
            if right == 0:
                raise EvaluationError("Division by zero", node)
            return left / right
        elif operator == 'mod':
            if right == 0:
                raise EvaluationError("Modulo by zero", node)
            return left % right
        
        else:
            raise EvaluationError(f"Unknown binary operator: {operator}", node)
    
    def _eval_and(self, node: BinaryOpNode) -> Optional[bool]:
        """
        Evaluate AND with short-circuit and three-valued logic.
        
        Truth table:
            True AND True = True
            True AND False = False
            True AND None = None
            False AND * = False
            None AND False = False
            None AND True = None
            None AND None = None
        """
        left = node.left.accept(self)
        
        # Short-circuit: False AND * = False
        if left is False:
            return False
        
        right = node.right.accept(self)
        
        # Short-circuit: * AND False = False
        if right is False:
            return False
        
        # Both true
        if left is True and right is True:
            return True
        
        # At least one null
        return None
    
    def _eval_or(self, node: BinaryOpNode) -> Optional[bool]:
        """
        Evaluate OR with short-circuit and three-valued logic.
        
        Truth table:
            True OR * = True
            False OR True = True
            False OR False = False
            False OR None = None
            None OR True = True
            None OR False = None
            None OR None = None
        """
        left = node.left.accept(self)
        
        # Short-circuit: True OR * = True
        if left is True:
            return True
        
        right = node.right.accept(self)
        
        # Short-circuit: * OR True = True
        if right is True:
            return True
        
        # Both false
        if left is False and right is False:
            return False
        
        # At least one null
        return None
    
    def _compare_eq(self, left: Any, right: Any) -> bool:
        """
        Equality comparison with case-insensitive strings.
        
        Args:
            left: Left operand
            right: Right operand
            
        Returns:
            True if equal
        """
        # Case-insensitive string comparison
        if isinstance(left, str) and isinstance(right, str):
            return left.lower() == right.lower()
        
        return left == right
    
    def _compare_ne(self, left: Any, right: Any) -> bool:
        """Not equal comparison."""
        return not self._compare_eq(left, right)
    
    def _compare_gt(self, left: Any, right: Any) -> bool:
        """Greater than comparison with numeric promotion."""
        left, right = self._promote_numeric(left, right)
        return left > right
    
    def _compare_ge(self, left: Any, right: Any) -> bool:
        """Greater than or equal comparison."""
        left, right = self._promote_numeric(left, right)
        return left >= right
    
    def _compare_lt(self, left: Any, right: Any) -> bool:
        """Less than comparison."""
        left, right = self._promote_numeric(left, right)
        return left < right
    
    def _compare_le(self, left: Any, right: Any) -> bool:
        """Less than or equal comparison."""
        left, right = self._promote_numeric(left, right)
        return left <= right
    
    def _promote_numeric(self, left: Any, right: Any) -> tuple:
        """
        Promote numeric types for comparison.
        
        Promotion rules:
        - int + int = int
        - int + float = float
        - float + float = float
        
        Args:
            left: Left operand
            right: Right operand
            
        Returns:
            Tuple of promoted values
        """
        # If either is float, promote both to float
        if isinstance(left, float) or isinstance(right, float):
            return (float(left), float(right))
        
        return (left, right)
    
    def visit_function_call(self, node: FunctionCallNode) -> Any:
        """
        Visit function call node.
        
        Evaluates arguments and calls the function through registry.
        
        Args:
            node: Function call node
            
        Returns:
            Function result
            
        Raises:
            EvaluationError: If function not found or execution fails
        """
        # Evaluate arguments
        args = [arg.accept(self) for arg in node.arguments]
        
        try:
            # Call function through registry
            result = self.function_registry.call(node.function_name, args)
            return result
        except Exception as e:
            raise EvaluationError(
                f"Function call failed: {node.function_name}({args}): {e}",
                node
            )


class QueryEvaluator:
    """
    High-performance query evaluator with timeout and projection support.
    
    Provides entity filtering, projection, and pagination with configurable
    performance limits and memory efficiency.
    
    Features:
        - Stream-based entity filtering
        - Projection (select specific properties)
        - Pagination with top/skip
        - Query timeout protection
        - Performance metrics
    
    Example:
        >>> evaluator = QueryEvaluator(timeout_ms=5000)
        >>> entities = [
        ...     {'PartitionKey': 'P1', 'RowKey': 'R1', 'Price': 100},
        ...     {'PartitionKey': 'P1', 'RowKey': 'R2', 'Price': 50}
        ... ]
        >>> filtered = evaluator.filter_entities(ast, entities)
        >>> print(list(filtered))
    """
    
    def __init__(
        self,
        timeout_ms: float = 30000,
        type_validator: Optional[TypeValidator] = None,
        function_registry: Optional[FunctionRegistry] = None,
        case_sensitive_props: bool = False
    ):
        """
        Initialize query evaluator.
        
        Args:
            timeout_ms: Query execution timeout in milliseconds
            type_validator: Type validator for type checking
            function_registry: Function registry for function calls
            case_sensitive_props: Whether property names are case-sensitive
        """
        self.timeout_ms = timeout_ms
        self.type_validator = type_validator or TypeValidator()
        self.function_registry = function_registry or FunctionRegistry()
        self.case_sensitive_props = case_sensitive_props
        
        # Performance metrics
        self.entities_scanned = 0
        self.entities_filtered = 0
        self.evaluation_time_ms = 0.0
    
    def evaluate(self, filter_ast: Optional[ASTNode], entity: Dict[str, Any]) -> bool:
        """
        Evaluate filter expression against single entity.
        
        Args:
            filter_ast: Filter AST (None means no filter, return True)
            entity: Entity to evaluate
            
        Returns:
            True if entity matches filter, False otherwise
            
        Example:
            >>> result = evaluator.evaluate(ast, entity)
            >>> if result:
            ...     print("Entity matches!")
        """
        if filter_ast is None:
            return True
        
        evaluator = FilterEvaluator(
            entity=entity,
            type_validator=self.type_validator,
            function_registry=self.function_registry,
            case_sensitive_props=self.case_sensitive_props
        )
        
        result = filter_ast.accept(evaluator)
        
        # Handle three-valued logic: None is treated as False
        if result is None:
            return False
        
        return bool(result)
    
    def filter_entities(
        self,
        filter_ast: Optional[ASTNode],
        entities: List[Dict[str, Any]],
        top: Optional[int] = None,
        skip: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter entities with pagination support.
        
        Stream-based filtering for memory efficiency. Stops after 'top'
        entities found or timeout reached.
        
        Args:
            filter_ast: Filter AST (None for no filter)
            entities: Entities to filter
            top: Maximum entities to return
            skip: Number of entities to skip
            
        Returns:
            List of matching entities
            
        Raises:
            TimeoutError: If execution exceeds timeout
            
        Example:
            >>> # Get first 10 matching entities
            >>> results = evaluator.filter_entities(ast, entities, top=10)
        """
        start_time = time.time()
        results = []
        skipped = 0
        
        self.entities_scanned = 0
        self.entities_filtered = 0
        
        for entity in entities:
            # Check timeout
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self.timeout_ms:
                self.evaluation_time_ms = elapsed_ms
                raise TimeoutError(elapsed_ms, self.timeout_ms)
            
            self.entities_scanned += 1
            
            # Evaluate filter
            if self.evaluate(filter_ast, entity):
                # Handle skip
                if skip and skipped < skip:
                    skipped += 1
                    continue
                
                self.entities_filtered += 1
                results.append(entity)
                
                # Handle top
                if top and len(results) >= top:
                    break
        
        self.evaluation_time_ms = (time.time() - start_time) * 1000
        return results
    
    def project_entity(
        self,
        entity: Dict[str, Any],
        select_properties: Optional[List[str]] = None,
        always_include: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Project entity to include only requested properties.
        
        Always includes system properties (PartitionKey, RowKey, Timestamp)
        plus any properties in always_include set.
        
        Args:
            entity: Entity to project
            select_properties: Properties to include (None for all)
            always_include: Properties to always include
            
        Returns:
            Projected entity dictionary
            
        Example:
            >>> projected = evaluator.project_entity(
            ...     entity,
            ...     select_properties=['Name', 'Price'],
            ...     always_include={'PartitionKey', 'RowKey'}
            ... )
        """
        if select_properties is None:
            # No projection, return all properties
            return entity.copy()
        
        # Build set of properties to include
        include_props = set(select_properties)
        
        # Always include system properties
        system_props = {'PartitionKey', 'RowKey', 'Timestamp'}
        include_props.update(system_props)
        
        # Always include specified properties
        if always_include:
            include_props.update(always_include)
        
        # Project entity
        projected = {}
        for key, value in entity.items():
            # Case-insensitive property matching if configured
            if not self.case_sensitive_props:
                if any(key.lower() == prop.lower() for prop in include_props):
                    projected[key] = value
            else:
                if key in include_props:
                    projected[key] = value
        
        return projected
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get evaluation performance metrics.
        
        Returns:
            Dictionary with performance metrics
            
        Example:
            >>> metrics = evaluator.get_metrics()
            >>> print(f"Scanned: {metrics['entities_scanned']}")
            >>> print(f"Matched: {metrics['entities_filtered']}")
            >>> print(f"Time: {metrics['evaluation_time_ms']:.2f}ms")
        """
        return {
            'entities_scanned': self.entities_scanned,
            'entities_filtered': self.entities_filtered,
            'evaluation_time_ms': self.evaluation_time_ms,
            'timeout_ms': self.timeout_ms,
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.entities_scanned = 0
        self.entities_filtered = 0
        self.evaluation_time_ms = 0.0
