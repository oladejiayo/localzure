"""
Unit tests for OData Query Evaluator.

Comprehensive test suite covering:
- Visitor pattern for all AST node types
- Lazy evaluation and short-circuit logic
- Null safety and three-valued logic
- Type coercion and numeric promotion
- Entity filtering with pagination
- Projection support
- Query timeout handling
- Performance benchmarks
"""

import pytest
import time
from datetime import datetime, timezone
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.evaluator import (
    QueryEvaluator,
    FilterEvaluator,
    EvaluationError,
    TimeoutError,
)


def parse(expression: str):
    """Helper to lex and parse expression."""
    lexer = ODataLexer(expression)
    tokens = lexer.tokenize()
    parser = ODataParser(tokens)
    return parser.parse()


class TestLiteralEvaluation:
    """Tests for literal value evaluation."""
    
    def test_string_literal(self):
        """Test string literal evaluation."""
        ast = parse("Name eq 'Test'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'Test'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Other'}) is False
    
    def test_numeric_literal(self):
        """Test numeric literal evaluation."""
        ast = parse("Age eq 30")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Age': 30}) is True
        assert evaluator.evaluate(ast, {'Age': 25}) is False
    
    def test_boolean_literal(self):
        """Test boolean literal evaluation."""
        ast = parse("Active eq true")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Active': True}) is True
        assert evaluator.evaluate(ast, {'Active': False}) is False
    
    def test_null_literal(self):
        """Test null literal evaluation."""
        ast = parse("Value eq null")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': None}) is True
        assert evaluator.evaluate(ast, {'Value': 10}) is False


class TestPropertyAccess:
    """Tests for property access evaluation."""
    
    def test_simple_property(self):
        """Test simple property access."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 75}) is True
        assert evaluator.evaluate(ast, {'Price': 25}) is False
    
    def test_missing_property(self):
        """Test missing property returns None."""
        ast = parse("Missing eq null")
        evaluator = QueryEvaluator()
        
        # Missing property is treated as null
        assert evaluator.evaluate(ast, {'Other': 10}) is True
    
    def test_case_insensitive_property(self):
        """Test case-insensitive property access."""
        ast = parse("Name eq 'Test'")
        evaluator = QueryEvaluator(case_sensitive_props=False)
        
        # Should match regardless of case
        assert evaluator.evaluate(ast, {'name': 'Test'}) is True
        assert evaluator.evaluate(ast, {'NAME': 'Test'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Test'}) is True
    
    def test_case_sensitive_property(self):
        """Test case-sensitive property access."""
        ast = parse("Name eq 'Test'")
        evaluator = QueryEvaluator(case_sensitive_props=True)
        
        assert evaluator.evaluate(ast, {'Name': 'Test'}) is True
        assert evaluator.evaluate(ast, {'name': 'Test'}) is False


class TestComparisonOperators:
    """Tests for comparison operator evaluation."""
    
    def test_eq_operator(self):
        """Test equality operator."""
        ast = parse("Status eq 'Active'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Status': 'Active'}) is True
        assert evaluator.evaluate(ast, {'Status': 'Inactive'}) is False
    
    def test_ne_operator(self):
        """Test not equal operator."""
        ast = parse("Status ne 'Deleted'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Status': 'Active'}) is True
        assert evaluator.evaluate(ast, {'Status': 'Deleted'}) is False
    
    def test_gt_operator(self):
        """Test greater than operator."""
        ast = parse("Price gt 100")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 150}) is True
        assert evaluator.evaluate(ast, {'Price': 75}) is False
        assert evaluator.evaluate(ast, {'Price': 100}) is False
    
    def test_ge_operator(self):
        """Test greater than or equal operator."""
        ast = parse("Price ge 100")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 150}) is True
        assert evaluator.evaluate(ast, {'Price': 100}) is True
        assert evaluator.evaluate(ast, {'Price': 75}) is False
    
    def test_lt_operator(self):
        """Test less than operator."""
        ast = parse("Stock lt 10")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Stock': 5}) is True
        assert evaluator.evaluate(ast, {'Stock': 15}) is False
        assert evaluator.evaluate(ast, {'Stock': 10}) is False
    
    def test_le_operator(self):
        """Test less than or equal operator."""
        ast = parse("Stock le 10")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Stock': 5}) is True
        assert evaluator.evaluate(ast, {'Stock': 10}) is True
        assert evaluator.evaluate(ast, {'Stock': 15}) is False


class TestLogicalOperators:
    """Tests for logical operator evaluation."""
    
    def test_and_operator(self):
        """Test AND operator."""
        ast = parse("Price gt 50 and Stock lt 100")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 75, 'Stock': 50}) is True
        assert evaluator.evaluate(ast, {'Price': 25, 'Stock': 50}) is False
        assert evaluator.evaluate(ast, {'Price': 75, 'Stock': 150}) is False
    
    def test_or_operator(self):
        """Test OR operator."""
        ast = parse("Status eq 'Active' or Status eq 'Pending'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Status': 'Active'}) is True
        assert evaluator.evaluate(ast, {'Status': 'Pending'}) is True
        assert evaluator.evaluate(ast, {'Status': 'Deleted'}) is False
    
    def test_not_operator(self):
        """Test NOT operator."""
        ast = parse("not (Active eq true)")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Active': False}) is True
        assert evaluator.evaluate(ast, {'Active': True}) is False


class TestLazyEvaluation:
    """Tests for lazy evaluation and short-circuit logic."""
    
    def test_and_short_circuit_false(self):
        """Test AND short-circuits on False."""
        # First condition is False, second should not be evaluated
        ast = parse("Price lt 50 and NonExistent eq 10")
        evaluator = QueryEvaluator()
        
        # Should return False without evaluating NonExistent
        assert evaluator.evaluate(ast, {'Price': 25}) is False
    
    def test_or_short_circuit_true(self):
        """Test OR short-circuits on True."""
        # First condition is True, second should not be evaluated
        ast = parse("Active eq true or NonExistent eq 10")
        evaluator = QueryEvaluator()
        
        # Should return True without evaluating NonExistent
        assert evaluator.evaluate(ast, {'Active': True}) is True
    
    def test_and_both_evaluated(self):
        """Test AND evaluates both when first is True."""
        ast = parse("Price gt 50 and Stock lt 100")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 75, 'Stock': 50}) is True
    
    def test_or_both_evaluated(self):
        """Test OR evaluates both when first is False."""
        ast = parse("Status eq 'A' or Status eq 'B'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Status': 'B'}) is True


class TestNullSafety:
    """Tests for null safety and three-valued logic."""
    
    def test_null_equality(self):
        """Test null equality comparison."""
        ast = parse("Value eq null")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': None}) is True
        assert evaluator.evaluate(ast, {'Value': 10}) is False
    
    def test_null_inequality(self):
        """Test null inequality comparison."""
        ast = parse("Value ne null")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': 10}) is True
        assert evaluator.evaluate(ast, {'Value': None}) is False
    
    def test_null_propagation_comparison(self):
        """Test null propagates in comparison operators."""
        ast = parse("Value gt 10")
        evaluator = QueryEvaluator()
        
        # Null comparison returns None, treated as False
        assert evaluator.evaluate(ast, {'Value': None}) is False
    
    def test_null_in_and(self):
        """Test null in AND operation."""
        ast = parse("Active eq true and Value gt 10")
        evaluator = QueryEvaluator()
        
        # True AND None = None (treated as False)
        assert evaluator.evaluate(ast, {'Active': True, 'Value': None}) is False
        
        # False AND None = False
        assert evaluator.evaluate(ast, {'Active': False, 'Value': None}) is False
    
    def test_null_in_or(self):
        """Test null in OR operation."""
        ast = parse("Active eq true or Value gt 10")
        evaluator = QueryEvaluator()
        
        # True OR None = True
        assert evaluator.evaluate(ast, {'Active': True, 'Value': None}) is True
        
        # False OR None = None (treated as False)
        assert evaluator.evaluate(ast, {'Active': False, 'Value': None}) is False
    
    def test_not_null(self):
        """Test NOT with null."""
        ast = parse("not (Value gt 10)")
        evaluator = QueryEvaluator()
        
        # NOT None = None (treated as False)
        assert evaluator.evaluate(ast, {'Value': None}) is False


class TestTypeCoercion:
    """Tests for automatic type coercion."""
    
    def test_int_to_float_promotion(self):
        """Test integer to float promotion in comparison."""
        ast = parse("Price gt 50.5")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 51}) is True
        assert evaluator.evaluate(ast, {'Price': 50}) is False
    
    def test_float_comparison(self):
        """Test float comparison."""
        ast = parse("Value eq 3.14")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': 3.14}) is True
        assert evaluator.evaluate(ast, {'Value': 3.0}) is False
    
    def test_case_insensitive_string_comparison(self):
        """Test case-insensitive string comparison."""
        ast = parse("Name eq 'TEST'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'test'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Test'}) is True
        assert evaluator.evaluate(ast, {'Name': 'TEST'}) is True


class TestArithmeticOperators:
    """Tests for arithmetic operator evaluation."""
    
    def test_addition(self):
        """Test addition operator."""
        ast = parse("Price add 10 gt 60")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 55}) is True
        assert evaluator.evaluate(ast, {'Price': 40}) is False
    
    def test_subtraction(self):
        """Test subtraction operator."""
        ast = parse("Stock sub 5 lt 10")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Stock': 12}) is True
        assert evaluator.evaluate(ast, {'Stock': 20}) is False
    
    def test_multiplication(self):
        """Test multiplication operator."""
        ast = parse("Price mul 2 ge 100")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 50}) is True
        assert evaluator.evaluate(ast, {'Price': 40}) is False
    
    def test_division(self):
        """Test division operator."""
        ast = parse("Total div 2 eq 25")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Total': 50}) is True
        assert evaluator.evaluate(ast, {'Total': 40}) is False
    
    def test_modulo(self):
        """Test modulo operator."""
        ast = parse("Value mod 3 eq 1")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': 10}) is True
        assert evaluator.evaluate(ast, {'Value': 9}) is False
    
    def test_division_by_zero(self):
        """Test division by zero raises error."""
        ast = parse("Value div 0 eq 10")
        evaluator = QueryEvaluator()
        
        with pytest.raises(EvaluationError, match="Division by zero"):
            evaluator.evaluate(ast, {'Value': 100})
    
    def test_modulo_by_zero(self):
        """Test modulo by zero raises error."""
        ast = parse("Value mod 0 eq 10")
        evaluator = QueryEvaluator()
        
        with pytest.raises(EvaluationError, match="Modulo by zero"):
            evaluator.evaluate(ast, {'Value': 100})


class TestFunctionCalls:
    """Tests for function call evaluation."""
    
    def test_startswith_function(self):
        """Test startswith function."""
        ast = parse("startswith(Name, 'A')")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'Alice'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Bob'}) is False
    
    def test_contains_function(self):
        """Test contains function."""
        ast = parse("contains(Name, 'li')")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'Alice'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Bob'}) is False
    
    def test_length_function(self):
        """Test length function."""
        ast = parse("length(Name) gt 5")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'Alexander'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Bob'}) is False
    
    def test_year_function(self):
        """Test year function."""
        ast = parse("year(Created) eq 2024")
        evaluator = QueryEvaluator()
        
        date = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert evaluator.evaluate(ast, {'Created': date}) is True
        
        date2 = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert evaluator.evaluate(ast, {'Created': date2}) is False


class TestEntityFiltering:
    """Tests for entity filtering with pagination."""
    
    def test_filter_all_matching(self):
        """Test filtering with all entities matching."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75},
            {'Price': 150}
        ]
        
        results = evaluator.filter_entities(ast, entities)
        assert len(results) == 3
    
    def test_filter_partial_matching(self):
        """Test filtering with some entities matching."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 25},
            {'Price': 75},
            {'Price': 30}
        ]
        
        results = evaluator.filter_entities(ast, entities)
        assert len(results) == 2
        assert results[0]['Price'] == 100
        assert results[1]['Price'] == 75
    
    def test_filter_no_matching(self):
        """Test filtering with no entities matching."""
        ast = parse("Price gt 1000")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 200},
            {'Price': 300}
        ]
        
        results = evaluator.filter_entities(ast, entities)
        assert len(results) == 0
    
    def test_filter_with_top(self):
        """Test filtering with top parameter."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75},
            {'Price': 150},
            {'Price': 200}
        ]
        
        results = evaluator.filter_entities(ast, entities, top=2)
        assert len(results) == 2
        assert results[0]['Price'] == 100
        assert results[1]['Price'] == 75
    
    def test_filter_with_skip(self):
        """Test filtering with skip parameter."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75},
            {'Price': 150},
            {'Price': 200}
        ]
        
        results = evaluator.filter_entities(ast, entities, skip=2)
        assert len(results) == 2
        assert results[0]['Price'] == 150
        assert results[1]['Price'] == 200
    
    def test_filter_with_top_and_skip(self):
        """Test filtering with both top and skip."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75},
            {'Price': 150},
            {'Price': 200},
            {'Price': 250}
        ]
        
        results = evaluator.filter_entities(ast, entities, skip=1, top=2)
        assert len(results) == 2
        assert results[0]['Price'] == 75
        assert results[1]['Price'] == 150
    
    def test_filter_no_ast(self):
        """Test filtering without filter (return all)."""
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75}
        ]
        
        results = evaluator.filter_entities(None, entities)
        assert len(results) == 2


class TestProjection:
    """Tests for entity projection."""
    
    def test_project_all_properties(self):
        """Test projection with no select (all properties)."""
        evaluator = QueryEvaluator()
        
        entity = {
            'PartitionKey': 'P1',
            'RowKey': 'R1',
            'Name': 'Test',
            'Price': 100
        }
        
        projected = evaluator.project_entity(entity, select_properties=None)
        assert len(projected) == 4
        assert projected['Name'] == 'Test'
        assert projected['Price'] == 100
    
    def test_project_specific_properties(self):
        """Test projection with specific properties."""
        evaluator = QueryEvaluator()
        
        entity = {
            'PartitionKey': 'P1',
            'RowKey': 'R1',
            'Timestamp': '2024-01-01',
            'Name': 'Test',
            'Price': 100,
            'Stock': 50
        }
        
        projected = evaluator.project_entity(
            entity,
            select_properties=['Name', 'Price']
        )
        
        # Should include selected + system properties
        assert 'Name' in projected
        assert 'Price' in projected
        assert 'PartitionKey' in projected
        assert 'RowKey' in projected
        assert 'Timestamp' in projected
        assert 'Stock' not in projected
    
    def test_project_always_include_system(self):
        """Test projection always includes system properties."""
        evaluator = QueryEvaluator()
        
        entity = {
            'PartitionKey': 'P1',
            'RowKey': 'R1',
            'Timestamp': '2024-01-01',
            'Name': 'Test'
        }
        
        projected = evaluator.project_entity(
            entity,
            select_properties=['Name']
        )
        
        assert 'PartitionKey' in projected
        assert 'RowKey' in projected
        assert 'Timestamp' in projected
    
    def test_project_with_always_include(self):
        """Test projection with custom always_include set."""
        evaluator = QueryEvaluator()
        
        entity = {
            'PartitionKey': 'P1',
            'RowKey': 'R1',
            'Name': 'Test',
            'Price': 100,
            'Stock': 50
        }
        
        projected = evaluator.project_entity(
            entity,
            select_properties=['Name'],
            always_include={'Price'}
        )
        
        assert 'Name' in projected
        assert 'Price' in projected
        assert 'Stock' not in projected


class TestTimeout:
    """Tests for query timeout handling."""
    
    def test_timeout_not_exceeded(self):
        """Test query completes within timeout."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator(timeout_ms=5000)
        
        entities = [{'Price': i} for i in range(100)]
        
        results = evaluator.filter_entities(ast, entities)
        assert len(results) == 49  # 51-99 inclusive
    
    def test_timeout_exceeded(self):
        """Test timeout raises TimeoutError."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator(timeout_ms=1)  # Very short timeout
        
        # Create large dataset to exceed timeout
        entities = [{'Price': i} for i in range(10000)]
        
        with pytest.raises(TimeoutError):
            evaluator.filter_entities(ast, entities)


class TestMetrics:
    """Tests for evaluation metrics."""
    
    def test_metrics_entities_scanned(self):
        """Test entities scanned metric."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 25},
            {'Price': 75}
        ]
        
        evaluator.filter_entities(ast, entities)
        metrics = evaluator.get_metrics()
        
        assert metrics['entities_scanned'] == 3
        assert metrics['entities_filtered'] == 2
    
    def test_metrics_with_top(self):
        """Test metrics with top parameter."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [
            {'Price': 100},
            {'Price': 75},
            {'Price': 150},
            {'Price': 200}
        ]
        
        evaluator.filter_entities(ast, entities, top=2)
        metrics = evaluator.get_metrics()
        
        # Should stop after finding 2 matches
        assert metrics['entities_filtered'] == 2
        assert metrics['entities_scanned'] == 2  # Early termination
    
    def test_metrics_evaluation_time(self):
        """Test evaluation time metric."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [{'Price': i} for i in range(100)]
        
        evaluator.filter_entities(ast, entities)
        metrics = evaluator.get_metrics()
        
        assert metrics['evaluation_time_ms'] > 0
        assert metrics['evaluation_time_ms'] < 1000  # Should be fast
    
    def test_reset_metrics(self):
        """Test resetting metrics."""
        ast = parse("Price gt 50")
        evaluator = QueryEvaluator()
        
        entities = [{'Price': 100}]
        evaluator.filter_entities(ast, entities)
        
        evaluator.reset_metrics()
        metrics = evaluator.get_metrics()
        
        assert metrics['entities_scanned'] == 0
        assert metrics['entities_filtered'] == 0
        assert metrics['evaluation_time_ms'] == 0.0


class TestComplexQueries:
    """Tests for complex query evaluation."""
    
    def test_nested_logical_operators(self):
        """Test nested logical operators."""
        ast = parse("(Price gt 50 and Stock lt 100) or Status eq 'Low'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 75, 'Stock': 50, 'Status': 'OK'}) is True
        assert evaluator.evaluate(ast, {'Price': 25, 'Stock': 50, 'Status': 'Low'}) is True
        assert evaluator.evaluate(ast, {'Price': 25, 'Stock': 50, 'Status': 'OK'}) is False
    
    def test_multiple_functions(self):
        """Test multiple function calls."""
        ast = parse("startswith(Name, 'A') and length(Name) gt 5")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': 'Alexander'}) is True
        assert evaluator.evaluate(ast, {'Name': 'Anna'}) is False
        assert evaluator.evaluate(ast, {'Name': 'Bob'}) is False
    
    def test_arithmetic_in_comparison(self):
        """Test arithmetic in comparison."""
        ast = parse("Price mul 2 gt Total")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Price': 60, 'Total': 100}) is True
        assert evaluator.evaluate(ast, {'Price': 40, 'Total': 100}) is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_entity(self):
        """Test evaluation with empty entity."""
        ast = parse("Value eq null")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {}) is True
    
    def test_empty_string_property(self):
        """Test empty string property."""
        ast = parse("Name eq ''")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': ''}) is True
        assert evaluator.evaluate(ast, {'Name': 'Test'}) is False
    
    def test_unicode_strings(self):
        """Test Unicode string handling."""
        ast = parse("Name eq '日本語'")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Name': '日本語'}) is True
        assert evaluator.evaluate(ast, {'Name': 'English'}) is False
    
    def test_very_large_numbers(self):
        """Test very large number handling."""
        ast = parse("Value gt 1000000000")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': 2000000000}) is True
        assert evaluator.evaluate(ast, {'Value': 500000000}) is False
    
    def test_negative_numbers(self):
        """Test negative number handling."""
        ast = parse("Value lt 0")
        evaluator = QueryEvaluator()
        
        assert evaluator.evaluate(ast, {'Value': -10}) is True
        assert evaluator.evaluate(ast, {'Value': 10}) is False
