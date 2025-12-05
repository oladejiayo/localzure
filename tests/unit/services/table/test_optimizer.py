"""
Unit tests for OData Query Optimizer.

Comprehensive test suite covering:
- Point query detection
- Partition scan detection
- Range query detection
- Table scan detection
- Filter simplification
- Cost estimation
- Query plan caching
- Edge cases and error handling
"""

import pytest
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.optimizer import (
    QueryOptimizer,
    QueryPlan,
    QueryPlanType,
    PointQueryPlan,
    PartitionScanPlan,
    RangeQueryPlan,
    TableScanPlan,
    KeyExtractor,
    FilterSimplifier,
    CostEstimator
)


def parse(expression: str):
    """Helper to lex and parse expression."""
    lexer = ODataLexer(expression)
    tokens = lexer.tokenize()
    parser = ODataParser(tokens)
    return parser.parse()


class TestPointQueryDetection:
    """Tests for point query detection (PartitionKey eq X and RowKey eq Y)."""
    
    def test_simple_point_query(self):
        """Test basic point query detection."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key == 'R1'
        assert plan.filter_ast is None
        assert plan.estimated_cost == 1.0
    
    def test_point_query_reverse_order(self):
        """Test point query with RowKey first."""
        ast = parse("RowKey eq 'R1' and PartitionKey eq 'P1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key == 'R1'
    
    def test_point_query_with_additional_filter(self):
        """Test point query with extra predicates."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1' and Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key == 'R1'
        assert plan.filter_ast is not None
        assert plan.estimated_cost > 1.0  # Additional filter adds cost
    
    def test_point_query_numeric_keys(self):
        """Test point query with numeric key values."""
        ast = parse("PartitionKey eq '123' and RowKey eq '456'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == '123'
        assert plan.row_key == '456'
    
    def test_point_query_special_chars(self):
        """Test point query with special characters in keys."""
        ast = parse("PartitionKey eq 'P-1_2' and RowKey eq 'R:1/2'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P-1_2'
        assert plan.row_key == 'R:1/2'


class TestPartitionScanDetection:
    """Tests for partition scan detection (PartitionKey eq X)."""
    
    def test_simple_partition_scan(self):
        """Test basic partition scan detection."""
        ast = parse("PartitionKey eq 'P1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is None
        assert plan.estimated_cost == 10.0
    
    def test_partition_scan_with_filter(self):
        """Test partition scan with additional filter."""
        ast = parse("PartitionKey eq 'P1' and Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is not None
        assert plan.estimated_cost > 10.0
    
    def test_partition_scan_complex_filter(self):
        """Test partition scan with complex filter."""
        ast = parse("PartitionKey eq 'P1' and (Price gt 100 and Stock lt 50)")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is not None
    
    def test_partition_scan_function_filter(self):
        """Test partition scan with function in filter."""
        ast = parse("PartitionKey eq 'P1' and startswith(Name, 'A')")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is not None


class TestRangeQueryDetection:
    """Tests for range query detection (PartitionKey eq X and RowKey bounds)."""
    
    def test_range_query_gt(self):
        """Test range query with RowKey gt."""
        ast = parse("PartitionKey eq 'P1' and RowKey gt 'R5'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_start == 'R5'
        assert plan.row_key_end is None
        assert plan.start_inclusive is False
    
    def test_range_query_ge(self):
        """Test range query with RowKey ge."""
        ast = parse("PartitionKey eq 'P1' and RowKey ge 'R5'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_start == 'R5'
        assert plan.start_inclusive is True
    
    def test_range_query_lt(self):
        """Test range query with RowKey lt."""
        ast = parse("PartitionKey eq 'P1' and RowKey lt 'R9'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_start is None
        assert plan.row_key_end == 'R9'
        assert plan.end_inclusive is False
    
    def test_range_query_le(self):
        """Test range query with RowKey le."""
        ast = parse("PartitionKey eq 'P1' and RowKey le 'R9'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_end == 'R9'
        assert plan.end_inclusive is True
    
    def test_range_query_both_bounds(self):
        """Test range query with both lower and upper bounds."""
        ast = parse("PartitionKey eq 'P1' and RowKey ge 'R5' and RowKey lt 'R9'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_start == 'R5'
        assert plan.row_key_end == 'R9'
        assert plan.start_inclusive is True
        assert plan.end_inclusive is False
    
    def test_range_query_with_filter(self):
        """Test range query with additional filter."""
        ast = parse("PartitionKey eq 'P1' and RowKey gt 'R5' and Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, RangeQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key_start == 'R5'
        assert plan.filter_ast is not None


class TestTableScanDetection:
    """Tests for table scan detection (no partition key)."""
    
    def test_simple_table_scan(self):
        """Test basic table scan (no filter)."""
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(None)
        
        assert isinstance(plan, TableScanPlan)
        assert plan.filter_ast is None
        assert plan.estimated_cost == 100.0
    
    def test_table_scan_with_filter(self):
        """Test table scan with filter."""
        ast = parse("Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, TableScanPlan)
        assert plan.filter_ast is not None
        assert plan.estimated_cost > 100.0
    
    def test_table_scan_complex_filter(self):
        """Test table scan with complex filter."""
        ast = parse("Price gt 100 and (Stock lt 50 or Status eq 'Low')")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, TableScanPlan)
        assert plan.filter_ast is not None
    
    def test_table_scan_row_key_only(self):
        """Test table scan when only RowKey is specified."""
        ast = parse("RowKey eq 'R1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # Without PartitionKey, this is a table scan
        assert isinstance(plan, TableScanPlan)
        assert plan.filter_ast is not None


class TestKeyExtractor:
    """Tests for KeyExtractor visitor."""
    
    def test_extract_partition_key(self):
        """Test extracting partition key."""
        ast = parse("PartitionKey eq 'P1'")
        extractor = KeyExtractor()
        ast.accept(extractor)
        
        assert extractor.partition_key == 'P1'
        assert extractor.row_key is None
    
    def test_extract_row_key(self):
        """Test extracting row key."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        extractor = KeyExtractor()
        ast.accept(extractor)
        
        assert extractor.partition_key == 'P1'
        assert extractor.row_key == 'R1'
    
    def test_extract_row_key_ranges(self):
        """Test extracting row key ranges."""
        ast = parse("PartitionKey eq 'P1' and RowKey ge 'R5' and RowKey lt 'R9'")
        extractor = KeyExtractor()
        ast.accept(extractor)
        
        assert extractor.partition_key == 'P1'
        assert extractor.row_key_ge == 'R5'
        assert extractor.row_key_lt == 'R9'
    
    def test_detect_other_predicates(self):
        """Test detection of non-key predicates."""
        ast = parse("PartitionKey eq 'P1' and Active eq true")
        extractor = KeyExtractor()
        ast.accept(extractor)
        
        assert extractor.partition_key == 'P1'
        assert extractor.has_other_predicates is True


class TestFilterSimplifier:
    """Tests for FilterSimplifier visitor."""
    
    def test_remove_partition_key(self):
        """Test removing partition key constraint."""
        ast = parse("PartitionKey eq 'P1' and Active eq true")
        simplifier = FilterSimplifier(partition_key='P1')
        result = ast.accept(simplifier)
        
        assert result is not None
        assert 'Active' in str(result)
        assert 'PartitionKey' not in str(result)
    
    def test_remove_both_keys(self):
        """Test removing both partition and row key."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1' and Active eq true")
        simplifier = FilterSimplifier(partition_key='P1', row_key='R1')
        result = ast.accept(simplifier)
        
        assert result is not None
        assert 'Active' in str(result)
        assert 'PartitionKey' not in str(result)
        assert 'RowKey' not in str(result)
    
    def test_remove_all_constraints(self):
        """Test removing all constraints leaves None."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        simplifier = FilterSimplifier(partition_key='P1', row_key='R1')
        result = ast.accept(simplifier)
        
        assert result is None
    
    def test_remove_row_key_ranges(self):
        """Test removing row key range constraints."""
        ast = parse("PartitionKey eq 'P1' and RowKey ge 'R5' and Active eq true")
        simplifier = FilterSimplifier(partition_key='P1', remove_row_key_ranges=True)
        result = ast.accept(simplifier)
        
        assert result is not None
        assert 'Active' in str(result)
        assert 'RowKey' not in str(result)


class TestCostEstimator:
    """Tests for CostEstimator."""
    
    def test_point_query_cost(self):
        """Test point query cost estimation."""
        cost = CostEstimator.estimate(QueryPlanType.POINT_QUERY, None)
        assert cost == 1.0
    
    def test_partition_scan_cost(self):
        """Test partition scan cost estimation."""
        cost = CostEstimator.estimate(QueryPlanType.PARTITION_SCAN, None)
        assert cost == 10.0
    
    def test_range_query_cost(self):
        """Test range query cost estimation."""
        cost = CostEstimator.estimate(QueryPlanType.RANGE_QUERY, None)
        assert cost == 15.0
    
    def test_table_scan_cost(self):
        """Test table scan cost estimation."""
        cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, None)
        assert cost == 100.0
    
    def test_filter_adds_cost(self):
        """Test that filters increase cost."""
        ast = parse("Active eq true")
        cost_no_filter = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, None)
        cost_with_filter = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, ast)
        
        assert cost_with_filter > cost_no_filter
    
    def test_complex_filter_higher_cost(self):
        """Test that complex filters have higher cost."""
        simple = parse("Active eq true")
        complex_ast = parse("Price gt 100 and Stock lt 50 and Status eq 'Low'")
        
        simple_cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, simple)
        complex_cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, complex_ast)
        
        assert complex_cost > simple_cost
    
    def test_function_call_cost(self):
        """Test that function calls add significant cost."""
        simple = parse("Name eq 'Test'")
        with_func = parse("startswith(Name, 'T')")
        
        simple_cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, simple)
        func_cost = CostEstimator.estimate(QueryPlanType.TABLE_SCAN, with_func)
        
        assert func_cost > simple_cost


class TestQueryPlanCaching:
    """Tests for query plan caching."""
    
    def test_cache_hit_same_query(self):
        """Test cache hit for identical queries."""
        optimizer = QueryOptimizer()
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        
        plan1 = optimizer.optimize(ast)
        plan2 = optimizer.optimize(ast)
        
        # Should be the exact same cached instance
        assert plan1 is plan2
        
        stats = optimizer.get_cache_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 1
    
    def test_cache_miss_different_query(self):
        """Test cache miss for different queries."""
        optimizer = QueryOptimizer()
        
        ast1 = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        ast2 = parse("PartitionKey eq 'P2' and RowKey eq 'R2'")
        
        plan1 = optimizer.optimize(ast1)
        plan2 = optimizer.optimize(ast2)
        
        assert plan1 is not plan2
        
        stats = optimizer.get_cache_stats()
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 2
    
    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        optimizer = QueryOptimizer()
        ast = parse("PartitionKey eq 'P1'")
        
        # First call: cache miss
        optimizer.optimize(ast)
        # Subsequent calls: cache hits
        optimizer.optimize(ast)
        optimizer.optimize(ast)
        optimizer.optimize(ast)
        
        stats = optimizer.get_cache_stats()
        assert stats['cache_hits'] == 3
        assert stats['cache_misses'] == 1
        assert stats['hit_rate'] == 0.75
    
    def test_cache_clear(self):
        """Test clearing the cache."""
        optimizer = QueryOptimizer()
        ast = parse("PartitionKey eq 'P1'")
        
        optimizer.optimize(ast)
        optimizer.clear_cache()
        
        stats = optimizer.get_cache_stats()
        assert stats['cache_size'] == 0
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0
    
    def test_cache_eviction(self):
        """Test cache eviction when full."""
        optimizer = QueryOptimizer(cache_size=2)
        
        ast1 = parse("PartitionKey eq 'P1'")
        ast2 = parse("PartitionKey eq 'P2'")
        ast3 = parse("PartitionKey eq 'P3'")
        
        optimizer.optimize(ast1)
        optimizer.optimize(ast2)
        optimizer.optimize(ast3)  # Should evict oldest
        
        stats = optimizer.get_cache_stats()
        assert stats['cache_size'] == 2


class TestComplexQueries:
    """Tests for complex query optimization."""
    
    def test_nested_and_conditions(self):
        """Test optimization with nested AND conditions."""
        ast = parse("((PartitionKey eq 'P1' and RowKey eq 'R1') and Active eq true)")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P1'
        assert plan.row_key == 'R1'
    
    def test_multiple_comparisons(self):
        """Test optimization with multiple comparison operators."""
        ast = parse("PartitionKey eq 'P1' and Price gt 100 and Stock lt 50")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is not None
    
    def test_arithmetic_in_filter(self):
        """Test optimization with arithmetic expressions."""
        ast = parse("PartitionKey eq 'P1' and Price mul 2 gt 200")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
    
    def test_function_calls_in_filter(self):
        """Test optimization with function calls."""
        ast = parse("PartitionKey eq 'P1' and startswith(Name, 'A') and endswith(Name, 'Z')")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
        assert plan.filter_ast is not None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_partition_key(self):
        """Test with empty partition key value."""
        ast = parse("PartitionKey eq ''")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # Empty partition key is still optimized as partition scan
        # (Azure Table Storage allows empty partition keys)
        assert isinstance(plan, (PartitionScanPlan, TableScanPlan))
        if isinstance(plan, PartitionScanPlan):
            assert plan.partition_key == ''
    
    def test_very_long_key_values(self):
        """Test with very long key values."""
        long_key = 'K' * 1000
        ast = parse(f"PartitionKey eq '{long_key}'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == long_key
    
    def test_unicode_key_values(self):
        """Test with Unicode key values."""
        ast = parse("PartitionKey eq '日本語' and RowKey eq '中文'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == '日本語'
        assert plan.row_key == '中文'
    
    def test_special_characters_in_keys(self):
        """Test with special characters in keys."""
        ast = parse("PartitionKey eq 'P@1#2$3' and RowKey eq 'R%4^5&6'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        assert isinstance(plan, PointQueryPlan)
        assert plan.partition_key == 'P@1#2$3'
        assert plan.row_key == 'R%4^5&6'


class TestPlanTypes:
    """Tests for query plan type hierarchy."""
    
    def test_point_query_plan_str(self):
        """Test PointQueryPlan string representation."""
        ast = parse("PartitionKey eq 'P1' and RowKey eq 'R1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        plan_str = str(plan)
        assert 'PointQuery' in plan_str
        assert 'P1' in plan_str
        assert 'R1' in plan_str
    
    def test_partition_scan_plan_str(self):
        """Test PartitionScanPlan string representation."""
        ast = parse("PartitionKey eq 'P1'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        plan_str = str(plan)
        assert 'PartitionScan' in plan_str
        assert 'P1' in plan_str
    
    def test_range_query_plan_str(self):
        """Test RangeQueryPlan string representation."""
        ast = parse("PartitionKey eq 'P1' and RowKey ge 'R5' and RowKey lt 'R9'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        plan_str = str(plan)
        assert 'RangeQuery' in plan_str
        assert 'P1' in plan_str
        assert 'R5' in plan_str
        assert 'R9' in plan_str
    
    def test_table_scan_plan_str(self):
        """Test TableScanPlan string representation."""
        ast = parse("Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        plan_str = str(plan)
        assert 'TableScan' in plan_str
    
    def test_plan_type_enum(self):
        """Test QueryPlanType enum."""
        assert str(QueryPlanType.POINT_QUERY) == 'point_query'
        assert str(QueryPlanType.PARTITION_SCAN) == 'partition_scan'
        assert str(QueryPlanType.RANGE_QUERY) == 'range_query'
        assert str(QueryPlanType.TABLE_SCAN) == 'table_scan'


class TestOrOperatorFallback:
    """Tests for OR operator fallback to table scan."""
    
    def test_or_prevents_point_query(self):
        """Test that OR prevents point query optimization."""
        ast = parse("(PartitionKey eq 'P1' and RowKey eq 'R1') or Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # OR at top level prevents optimization
        assert isinstance(plan, TableScanPlan)
    
    def test_or_prevents_partition_scan(self):
        """Test that OR prevents partition scan optimization."""
        ast = parse("PartitionKey eq 'P1' or PartitionKey eq 'P2'")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # OR between partition keys prevents optimization
        assert isinstance(plan, TableScanPlan)


class TestNotOperatorHandling:
    """Tests for NOT operator handling."""
    
    def test_not_prevents_optimization(self):
        """Test that NOT prevents key-based optimization."""
        ast = parse("not (PartitionKey eq 'P1')")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # NOT operator prevents optimization
        assert isinstance(plan, TableScanPlan)
    
    def test_not_in_additional_filter(self):
        """Test NOT in additional filter after key extraction."""
        ast = parse("PartitionKey eq 'P1' and not Active eq true")
        optimizer = QueryOptimizer()
        plan = optimizer.optimize(ast)
        
        # Should still optimize partition scan, but mark as having other predicates
        assert isinstance(plan, PartitionScanPlan)
        assert plan.partition_key == 'P1'
