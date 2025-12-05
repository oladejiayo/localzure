"""
Unit tests for Error Handling & Diagnostics.

Comprehensive test suite covering:
- Error hierarchy and error codes
- Error message formatting
- Query validation
- Metrics collection
- Logging integration
- Suggestions for common mistakes
"""

import pytest
import logging
from localzure.services.table.lexer import ODataLexer, Position
from localzure.services.table.parser import ODataParser
from localzure.services.table.diagnostics import (
    ODataErrorCode,
    ODataQueryError,
    QuerySyntaxError,
    QueryTypeError,
    QueryFunctionError,
    QueryValidationError,
    QueryResourceError,
    QueryTimeoutError,
    QueryValidator,
    MetricsCollector,
    QueryLogger,
    ErrorFormatter,
)


def parse(expression: str):
    """Helper to lex and parse expression."""
    lexer = ODataLexer(expression)
    tokens = lexer.tokenize()
    parser = ODataParser(tokens)
    return parser.parse()


class TestErrorCodes:
    """Tests for error code enumeration."""
    
    def test_error_code_values(self):
        """Test error code string values."""
        assert str(ODataErrorCode.INVALID_INPUT) == "InvalidInput"
        assert str(ODataErrorCode.OPERATION_TIMED_OUT) == "OperationTimedOut"
        assert str(ODataErrorCode.OUT_OF_RANGE_INPUT) == "OutOfRangeInput"
    
    def test_all_error_codes(self):
        """Test all error codes are defined."""
        codes = [
            ODataErrorCode.INVALID_INPUT,
            ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            ODataErrorCode.OUT_OF_RANGE_INPUT,
            ODataErrorCode.INVALID_URI,
            ODataErrorCode.RESOURCE_NOT_FOUND,
            ODataErrorCode.OPERATION_TIMED_OUT,
            ODataErrorCode.REQUEST_BODY_TOO_LARGE,
            ODataErrorCode.INTERNAL_ERROR,
        ]
        assert len(codes) == 8


class TestODataQueryError:
    """Tests for base ODataQueryError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = ODataQueryError("Test error")
        
        assert error.message == "Test error"
        assert error.error_code == ODataErrorCode.INVALID_INPUT
        assert error.position is None
        assert error.suggestion is None
    
    def test_error_with_position(self):
        """Test error with position info."""
        pos = Position(line=1, column=10, offset=10)
        error = ODataQueryError("Test error", position=pos)
        
        assert error.position == pos
        assert "line 1" in str(error)
        assert "column 10" in str(error)
    
    def test_error_with_suggestion(self):
        """Test error with suggestion."""
        error = ODataQueryError(
            "Unknown operator",
            suggestion="Did you mean 'and'?"
        )
        
        assert error.suggestion == "Did you mean 'and'?"
        assert "Suggestion:" in str(error)
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        pos = Position(line=1, column=10, offset=10)
        error = ODataQueryError(
            "Test error",
            error_code=ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            position=pos,
            suggestion="Try this",
            context={'detail': 'Extra info'}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict['code'] == 'InvalidQueryParameterValue'
        assert error_dict['message'] == 'Test error'
        assert error_dict['position']['line'] == 1
        assert error_dict['suggestion'] == 'Try this'
        assert error_dict['context']['detail'] == 'Extra info'
    
    def test_error_str_format(self):
        """Test error string formatting."""
        error = ODataQueryError("Test error")
        error_str = str(error)
        
        assert "OData Query Error:" in error_str
        assert "Test error" in error_str
        assert "InvalidInput" in error_str


class TestSpecificErrorTypes:
    """Tests for specific error subclasses."""
    
    def test_syntax_error(self):
        """Test QuerySyntaxError."""
        error = QuerySyntaxError(
            "Unexpected token",
            position=Position(1, 5, 5),
            suggestion="Check parentheses"
        )
        
        assert error.error_code == ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE
        assert error.message == "Unexpected token"
        assert error.suggestion == "Check parentheses"
    
    def test_type_error(self):
        """Test QueryTypeError."""
        error = QueryTypeError(
            "Type mismatch",
            expected_type="Edm.Int32",
            actual_type="Edm.String"
        )
        
        assert error.context['expected_type'] == "Edm.Int32"
        assert error.context['actual_type'] == "Edm.String"
    
    def test_function_error(self):
        """Test QueryFunctionError."""
        error = QueryFunctionError(
            "Unknown function",
            function_name="badFunc",
            suggestion="Did you mean 'contains'?"
        )
        
        assert error.context['function_name'] == "badFunc"
        assert error.suggestion == "Did you mean 'contains'?"
    
    def test_validation_error(self):
        """Test QueryValidationError."""
        error = QueryValidationError(
            "Invalid expression",
            suggestion="Add parentheses"
        )
        
        assert error.error_code == ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE
    
    def test_resource_error(self):
        """Test QueryResourceError."""
        error = QueryResourceError(
            "Limit exceeded",
            limit_type="complexity",
            limit_value=100,
            actual_value=150
        )
        
        assert error.error_code == ODataErrorCode.OUT_OF_RANGE_INPUT
        assert error.context['limit_type'] == "complexity"
        assert error.context['limit_value'] == 100
        assert error.context['actual_value'] == 150
    
    def test_timeout_error(self):
        """Test QueryTimeoutError."""
        error = QueryTimeoutError(elapsed_ms=5000, timeout_ms=3000)
        
        assert error.error_code == ODataErrorCode.OPERATION_TIMED_OUT
        assert "5000" in error.message
        assert "3000" in error.message
        assert error.context['elapsed_ms'] == 5000
        assert error.context['timeout_ms'] == 3000


class TestQueryValidator:
    """Tests for query validation."""
    
    def test_validate_simple_query(self):
        """Test validating simple query."""
        ast = parse("Price gt 50")
        validator = QueryValidator()
        
        # Should not raise
        validator.validate(ast)
    
    def test_validate_complex_query(self):
        """Test validating complex query."""
        ast = parse("Price gt 50 and Stock lt 100 and Active eq true")
        validator = QueryValidator()
        
        validator.validate(ast)
        assert validator.complexity > 0
    
    def test_validate_none_ast(self):
        """Test validating None AST."""
        validator = QueryValidator()
        
        # Should not raise
        validator.validate(None)
    
    def test_complexity_limit_exceeded(self):
        """Test complexity limit validation."""
        # Create deeply nested expression
        expr = "Price gt 50"
        for i in range(50):
            expr = f"({expr} and Stock gt {i})"
        
        ast = parse(expr)
        validator = QueryValidator(max_complexity=10)
        
        with pytest.raises(QueryResourceError) as exc_info:
            validator.validate(ast)
        
        error = exc_info.value
        assert error.context['limit_type'] == 'complexity'
        assert error.context['limit_value'] == 10
    
    def test_unknown_function_error(self):
        """Test unknown function validation."""
        from localzure.services.table.parser import FunctionCallNode, NodeType
        from localzure.services.table.lexer import Position
        
        # Create function call AST node directly (parser would reject invalid function)
        ast = FunctionCallNode(
            node_type=NodeType.FUNCTION_CALL,
            position=Position(1, 1, 0),
            function_name='badFunction',
            arguments=()
        )
        validator = QueryValidator()
        
        with pytest.raises(QueryFunctionError) as exc_info:
            validator.validate(ast)
        
        error = exc_info.value
        assert "badFunction" in error.message
        assert error.suggestion is not None
    
    def test_function_suggestion(self):
        """Test function name suggestion."""
        from localzure.services.table.parser import FunctionCallNode, NodeType
        from localzure.services.table.lexer import Position
        
        # Create function call with typo directly
        ast = FunctionCallNode(
            node_type=NodeType.FUNCTION_CALL,
            position=Position(1, 1, 0),
            function_name='conains',  # Typo: conains -> contains
            arguments=()
        )
        validator = QueryValidator()
        
        with pytest.raises(QueryFunctionError) as exc_info:
            validator.validate(ast)
        
        error = exc_info.value
        assert "contains" in error.suggestion.lower()
    
    def test_validate_known_functions(self):
        """Test validation passes for all known functions."""
        validator = QueryValidator()
        
        # Test a few known functions
        functions = ['startswith', 'length', 'year', 'round']
        
        for func in functions:
            ast = parse(f"{func}(Name)")
            validator.validate(ast)  # Should not raise


class TestMetricsCollector:
    """Tests for metrics collection."""
    
    def test_record_query(self):
        """Test recording query metrics."""
        metrics = MetricsCollector()
        
        query_id = metrics.record_query_start('point_query')
        metrics.record_query_end(
            query_id,
            duration_ms=1.5,
            entities_scanned=1,
            entities_returned=1
        )
        
        stats = metrics.get_statistics()
        assert stats['total_queries'] == 1
        assert stats['query_counts']['point_query'] == 1
        assert stats['latency_avg'] == 1.5
    
    def test_record_multiple_queries(self):
        """Test recording multiple queries."""
        metrics = MetricsCollector()
        
        for i in range(10):
            query_id = metrics.record_query_start('partition_scan')
            metrics.record_query_end(
                query_id,
                duration_ms=float(i + 1)
            )
        
        stats = metrics.get_statistics()
        assert stats['total_queries'] == 10
        assert stats['query_counts']['partition_scan'] == 10
    
    def test_latency_percentiles(self):
        """Test latency percentile calculation."""
        metrics = MetricsCollector()
        
        # Record 100 queries with known latencies
        for i in range(100):
            query_id = metrics.record_query_start('test')
            metrics.record_query_end(query_id, duration_ms=float(i))
        
        stats = metrics.get_statistics()
        
        assert stats['latency_p50'] >= 49  # Around 50th percentile
        assert stats['latency_p95'] >= 94  # Around 95th percentile
        assert stats['latency_p99'] >= 98  # Around 99th percentile
        assert stats['latency_max'] == 99
    
    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        metrics = MetricsCollector()
        
        # Record 10 queries: 7 hits, 3 misses
        for i in range(10):
            query_id = metrics.record_query_start('test')
            metrics.record_query_end(
                query_id,
                duration_ms=1.0,
                cache_hit=(i < 7)
            )
        
        stats = metrics.get_statistics()
        assert stats['cache_hits'] == 7
        assert stats['cache_misses'] == 3
        assert stats['cache_hit_rate'] == 0.7
    
    def test_error_tracking(self):
        """Test error rate tracking."""
        metrics = MetricsCollector()
        
        # Record 10 queries: 8 success, 2 errors
        for i in range(10):
            query_id = metrics.record_query_start('test')
            error = "TestError" if i >= 8 else None
            metrics.record_query_end(
                query_id,
                duration_ms=1.0,
                error=error
            )
        
        stats = metrics.get_statistics()
        assert stats['total_queries'] == 10
        assert stats['total_errors'] == 2
        assert stats['error_rate'] == 0.2
        assert stats['error_counts']['TestError'] == 2
    
    def test_entity_counts(self):
        """Test entity count tracking."""
        metrics = MetricsCollector()
        
        query_id = metrics.record_query_start('test')
        metrics.record_query_end(
            query_id,
            duration_ms=10.0,
            entities_scanned=100,
            entities_returned=25
        )
        
        stats = metrics.get_statistics()
        assert stats['total_entities_scanned'] == 100
        assert stats['total_entities_returned'] == 25
    
    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = MetricsCollector()
        
        query_id = metrics.record_query_start('test')
        metrics.record_query_end(query_id, duration_ms=1.0)
        
        metrics.reset()
        stats = metrics.get_statistics()
        
        assert stats['total_queries'] == 0
        assert stats['cache_hits'] == 0
        assert len(stats['query_counts']) == 0
    
    def test_query_type_breakdown(self):
        """Test query type breakdown."""
        metrics = MetricsCollector()
        
        metrics.record_query_end(
            metrics.record_query_start('point_query'),
            duration_ms=1.0
        )
        metrics.record_query_end(
            metrics.record_query_start('point_query'),
            duration_ms=1.0
        )
        metrics.record_query_end(
            metrics.record_query_start('partition_scan'),
            duration_ms=5.0
        )
        
        stats = metrics.get_statistics()
        assert stats['query_counts']['point_query'] == 2
        assert stats['query_counts']['partition_scan'] == 1


class TestQueryLogger:
    """Tests for query logging."""
    
    def test_log_query_start(self, caplog):
        """Test logging query start."""
        logger = QueryLogger()
        
        with caplog.at_level(logging.INFO):
            logger.log_query_start(
                "Price gt 50",
                query_type='partition_scan'
            )
        
        assert "Query started" in caplog.text
    
    def test_log_query_end(self, caplog):
        """Test logging query end."""
        logger = QueryLogger()
        
        with caplog.at_level(logging.INFO):
            logger.log_query_end(
                duration_ms=5.2,
                entities_scanned=100,
                entities_returned=25
            )
        
        assert "Query completed" in caplog.text
        assert "5.2" in caplog.text
    
    def test_log_error(self, caplog):
        """Test logging errors."""
        logger = QueryLogger()
        error = QuerySyntaxError("Test error")
        
        with caplog.at_level(logging.ERROR):
            logger.log_error(error, query_expression="Price gt 50")
        
        assert "Query error" in caplog.text
        assert "Test error" in caplog.text
    
    def test_log_odata_error(self, caplog):
        """Test logging ODataQueryError with details."""
        logger = QueryLogger()
        error = QueryFunctionError(
            "Unknown function",
            function_name="badFunc"
        )
        
        with caplog.at_level(logging.ERROR):
            logger.log_error(error)
        
        assert "Unknown function" in caplog.text
        assert "Query error" in caplog.text


class TestErrorFormatter:
    """Tests for error formatting."""
    
    def test_format_basic_error(self):
        """Test formatting basic error."""
        error = ODataQueryError("Test error")
        formatter = ErrorFormatter()
        
        formatted = formatter.format_error(error)
        assert "Test error" in formatted
        assert "InvalidInput" in formatted
    
    def test_format_error_with_source(self):
        """Test formatting error with source context."""
        pos = Position(line=1, column=10, offset=10)
        error = ODataQueryError("Test error", position=pos)
        formatter = ErrorFormatter()
        
        formatted = formatter.format_error(
            error,
            source="Price gt 50 and Active eq true"
        )
        
        assert "Query:" in formatted
        assert "Price gt 50 and Active eq true" in formatted
        assert "^" in formatted  # Position marker
    
    def test_format_error_with_suggestion(self):
        """Test formatting error with suggestion."""
        error = ODataQueryError(
            "Test error",
            suggestion="Try this instead"
        )
        formatter = ErrorFormatter()
        
        formatted = formatter.format_error(error)
        assert "Suggestion:" in formatted
        assert "Try this instead" in formatted
    
    def test_suggest_fix_typo(self):
        """Test suggesting fix for typo."""
        formatter = ErrorFormatter()
        known_tokens = ['and', 'or', 'not', 'eq', 'ne']
        
        suggestion = formatter.suggest_fix(
            "Unknown token: andd",
            known_tokens
        )
        
        assert suggestion is not None
        assert "and" in suggestion.lower()
    
    def test_suggest_fix_no_match(self):
        """Test no suggestion when no close match."""
        formatter = ErrorFormatter()
        known_tokens = ['and', 'or', 'not']
        
        suggestion = formatter.suggest_fix(
            "Unknown token: xyz123",
            known_tokens
        )
        
        # May or may not suggest, but shouldn't crash
        assert suggestion is None or isinstance(suggestion, str)


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_validate_and_collect_metrics(self):
        """Test validation with metrics collection."""
        ast = parse("Price gt 50 and Active eq true")
        
        validator = QueryValidator()
        validator.validate(ast)
        
        metrics = MetricsCollector()
        query_id = metrics.record_query_start('partition_scan')
        metrics.record_query_end(query_id, duration_ms=5.0)
        
        stats = metrics.get_statistics()
        assert stats['total_queries'] == 1
    
    def test_error_with_formatter(self):
        """Test error creation and formatting."""
        pos = Position(line=1, column=12, offset=12)
        error = QuerySyntaxError(
            "Unexpected token 'andd'",
            position=pos,
            suggestion="Did you mean 'and'?"
        )
        
        formatter = ErrorFormatter()
        formatted = formatter.format_error(
            error,
            source="Price gt 50 andd Active eq true"
        )
        
        assert "Unexpected token" in formatted
        assert "^" in formatted
        assert "Did you mean 'and'?" in formatted
    
    def test_full_query_lifecycle(self, caplog):
        """Test complete query lifecycle with all components."""
        # Parse and validate
        ast = parse("startswith(Name, 'A') and Price gt 100")
        
        validator = QueryValidator()
        validator.validate(ast)
        
        # Log and collect metrics
        logger = QueryLogger()
        metrics = MetricsCollector()
        
        with caplog.at_level(logging.INFO):
            logger.log_query_start(
                "startswith(Name, 'A') and Price gt 100",
                query_type='partition_scan'
            )
            
            query_id = metrics.record_query_start('partition_scan')
            # ... query execution would happen here ...
            metrics.record_query_end(
                query_id,
                duration_ms=8.5,
                entities_scanned=100,
                entities_returned=15,
                cache_hit=False
            )
            
            logger.log_query_end(
                duration_ms=8.5,
                entities_scanned=100,
                entities_returned=15
            )
        
        # Verify metrics
        stats = metrics.get_statistics()
        assert stats['total_queries'] == 1
        assert stats['latency_avg'] == 8.5
        
        # Verify logging
        assert "Query started" in caplog.text
        assert "Query completed" in caplog.text


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_metrics(self):
        """Test metrics with no queries."""
        metrics = MetricsCollector()
        stats = metrics.get_statistics()
        
        assert stats['total_queries'] == 0
        assert stats['error_rate'] == 0.0
        assert stats['cache_hit_rate'] == 0.0
        assert stats['latency_avg'] == 0.0
    
    def test_very_long_error_message(self):
        """Test very long error message."""
        long_message = "X" * 10000
        error = ODataQueryError(long_message)
        
        assert len(error.message) == 10000
        error_dict = error.to_dict()
        assert len(error_dict['message']) == 10000
    
    def test_unicode_in_errors(self):
        """Test Unicode characters in errors."""
        error = ODataQueryError("エラー: 無効なクエリ")
        
        assert "エラー" in error.message
        formatted = str(error)
        assert "エラー" in formatted
    
    def test_multiple_suggestions(self):
        """Test multiple function suggestions."""
        from localzure.services.table.parser import FunctionCallNode, NodeType
        from localzure.services.table.lexer import Position
        
        # Create function call with typo (close to contains, concat)
        ast = FunctionCallNode(
            node_type=NodeType.FUNCTION_CALL,
            position=Position(1, 1, 0),
            function_name='cont',
            arguments=()
        )
        validator = QueryValidator()
        
        with pytest.raises(QueryFunctionError) as exc_info:
            validator.validate(ast)
        
        error = exc_info.value
        assert error.suggestion is not None
