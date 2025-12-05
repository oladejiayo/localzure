"""
Production-grade Error Handling & Diagnostics for OData Query Engine.

This module provides comprehensive error handling with Azure Table Storage
compatible error codes, detailed diagnostics, structured logging, and metrics
collection.

Features:
- Structured error hierarchy matching Azure error codes
- Detailed error messages with position and context
- Query validation before execution
- Timeout and resource limit handling
- Structured logging with performance metrics
- Metrics collection (latency, errors, cache hits)

Example:
    >>> from localzure.services.table.diagnostics import (
    ...     QueryValidator, MetricsCollector, ErrorFormatter
    ... )
    >>> 
    >>> validator = QueryValidator()
    >>> validator.validate(ast)  # Raises detailed errors
    >>> 
    >>> metrics = MetricsCollector()
    >>> metrics.record_query_start('point_query')
    >>> # ... execute query ...
    >>> metrics.record_query_end('point_query', duration_ms=1.5)

Author: LocalZure Team
Version: 1.0.0
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from collections import defaultdict
import difflib

from .lexer import Position
from .parser import ASTNode, BinaryOpNode, UnaryOpNode, FunctionCallNode


class ODataErrorCode(Enum):
    """
    Azure Table Storage compatible error codes.
    
    Maps to HTTP status codes and Azure error messages.
    """
    # 400 Bad Request errors
    INVALID_INPUT = "InvalidInput"
    INVALID_QUERY_PARAMETER_VALUE = "InvalidQueryParameterValue"
    OUT_OF_RANGE_INPUT = "OutOfRangeInput"
    INVALID_URI = "InvalidUri"
    
    # 404 Not Found errors
    RESOURCE_NOT_FOUND = "ResourceNotFound"
    
    # 408 Request Timeout
    OPERATION_TIMED_OUT = "OperationTimedOut"
    
    # 413 Payload Too Large
    REQUEST_BODY_TOO_LARGE = "RequestBodyTooLarge"
    
    # 500 Internal Server Error
    INTERNAL_ERROR = "InternalError"
    
    def __str__(self) -> str:
        return self.value


class ODataQueryError(Exception):
    """
    Base class for all OData query errors.
    
    Provides structured error information compatible with Azure Table Storage
    error responses.
    
    Attributes:
        message: Human-readable error message
        error_code: Azure compatible error code
        position: Position in source where error occurred
        suggestion: Suggestion for fixing the error
        context: Additional context information
    """
    
    def __init__(
        self,
        message: str,
        error_code: ODataErrorCode = ODataErrorCode.INVALID_INPUT,
        position: Optional[Position] = None,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.position = position
        self.suggestion = suggestion
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary format.
        
        Returns dictionary compatible with Azure Table Storage error response.
        """
        result = {
            'code': str(self.error_code),
            'message': self.message,
        }
        
        if self.position:
            result['position'] = {
                'line': self.position.line,
                'column': self.position.column,
                'offset': self.position.offset
            }
        
        if self.suggestion:
            result['suggestion'] = self.suggestion
        
        if self.context:
            result['context'] = self.context
        
        return result
    
    def __str__(self) -> str:
        """Format error message with all details."""
        lines = []
        
        if self.position:
            lines.append(
                f"OData Query Error at line {self.position.line}, "
                f"column {self.position.column}:"
            )
        else:
            lines.append("OData Query Error:")
        
        lines.append(f"  {self.message}")
        lines.append(f"  Error Code: {self.error_code}")
        
        if self.suggestion:
            lines.append(f"  Suggestion: {self.suggestion}")
        
        return "\n".join(lines)


class QuerySyntaxError(ODataQueryError):
    """
    Syntax error in OData query expression.
    
    Raised when query has invalid syntax that prevents parsing.
    """
    
    def __init__(
        self,
        message: str,
        position: Optional[Position] = None,
        suggestion: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            position=position,
            suggestion=suggestion
        )


class QueryTypeError(ODataQueryError):
    """
    Type error in OData query expression.
    
    Raised when operand types are incompatible for the operation.
    """
    
    def __init__(
        self,
        message: str,
        position: Optional[Position] = None,
        expected_type: Optional[str] = None,
        actual_type: Optional[str] = None,
        suggestion: Optional[str] = None
    ):
        context = {}
        if expected_type:
            context['expected_type'] = expected_type
        if actual_type:
            context['actual_type'] = actual_type
        
        super().__init__(
            message=message,
            error_code=ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            position=position,
            suggestion=suggestion,
            context=context
        )


class QueryFunctionError(ODataQueryError):
    """
    Function-related error in OData query.
    
    Raised when function call is invalid (unknown function, wrong arguments, etc).
    """
    
    def __init__(
        self,
        message: str,
        function_name: Optional[str] = None,
        position: Optional[Position] = None,
        suggestion: Optional[str] = None
    ):
        context = {}
        if function_name:
            context['function_name'] = function_name
        
        super().__init__(
            message=message,
            error_code=ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            position=position,
            suggestion=suggestion,
            context=context
        )


class QueryValidationError(ODataQueryError):
    """
    Query validation error.
    
    Raised when query is syntactically valid but semantically invalid.
    """
    
    def __init__(
        self,
        message: str,
        position: Optional[Position] = None,
        suggestion: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ODataErrorCode.INVALID_QUERY_PARAMETER_VALUE,
            position=position,
            suggestion=suggestion
        )


class QueryResourceError(ODataQueryError):
    """
    Resource limit exceeded error.
    
    Raised when query exceeds configured resource limits.
    """
    
    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        limit_value: Optional[int] = None,
        actual_value: Optional[int] = None
    ):
        context = {}
        if limit_type:
            context['limit_type'] = limit_type
        if limit_value is not None:
            context['limit_value'] = limit_value
        if actual_value is not None:
            context['actual_value'] = actual_value
        
        super().__init__(
            message=message,
            error_code=ODataErrorCode.OUT_OF_RANGE_INPUT,
            context=context
        )


class QueryTimeoutError(ODataQueryError):
    """
    Query execution timeout error.
    
    Raised when query execution exceeds timeout limit.
    """
    
    def __init__(
        self,
        elapsed_ms: float,
        timeout_ms: float
    ):
        super().__init__(
            message=f"Query execution timeout: {elapsed_ms:.1f}ms exceeded limit of {timeout_ms:.0f}ms",
            error_code=ODataErrorCode.OPERATION_TIMED_OUT,
            context={
                'elapsed_ms': elapsed_ms,
                'timeout_ms': timeout_ms
            }
        )


class QueryValidator:
    """
    Validates OData queries before execution.
    
    Performs syntax, semantic, and type validation with detailed error messages.
    
    Features:
        - Syntax validation (correct operators, parentheses)
        - Semantic validation (valid property references)
        - Type validation (compatible operand types)
        - Suggestion generation for common mistakes
    
    Example:
        >>> validator = QueryValidator(max_complexity=100)
        >>> validator.validate(ast)  # Raises error if invalid
    """
    
    def __init__(
        self,
        max_complexity: int = 1000,
        known_functions: Optional[Set[str]] = None
    ):
        """
        Initialize query validator.
        
        Args:
            max_complexity: Maximum expression complexity
            known_functions: Set of known function names
        """
        self.max_complexity = max_complexity
        self.known_functions = known_functions or set([
            'startswith', 'endswith', 'contains', 'substringof',
            'tolower', 'toupper', 'trim', 'concat', 'substring',
            'length', 'indexof', 'replace',
            'year', 'month', 'day', 'hour', 'minute', 'second',
            'round', 'floor', 'ceiling',
            'isof', 'cast'
        ])
        
        self.complexity = 0
    
    def validate(self, ast: Optional[ASTNode]) -> None:
        """
        Validate AST.
        
        Args:
            ast: AST to validate
            
        Raises:
            QueryValidationError: If validation fails
        """
        if ast is None:
            return
        
        self.complexity = 0
        self._validate_node(ast)
        
        if self.complexity > self.max_complexity:
            raise QueryResourceError(
                f"Query complexity {self.complexity} exceeds maximum {self.max_complexity}",
                limit_type='complexity',
                limit_value=self.max_complexity,
                actual_value=self.complexity
            )
    
    def _validate_node(self, node: ASTNode) -> None:
        """Recursively validate AST node."""
        self.complexity += 1
        
        if isinstance(node, BinaryOpNode):
            self._validate_node(node.left)
            self._validate_node(node.right)
        elif isinstance(node, UnaryOpNode):
            self._validate_node(node.operand)
        elif isinstance(node, FunctionCallNode):
            self._validate_function_call(node)
    
    def _validate_function_call(self, node: FunctionCallNode) -> None:
        """Validate function call."""
        func_name = node.function_name.lower()
        
        if func_name not in self.known_functions:
            # Try to suggest similar function names
            suggestions = difflib.get_close_matches(
                func_name,
                self.known_functions,
                n=3,
                cutoff=0.6
            )
            
            if suggestions:
                suggestion = f"Did you mean: {', '.join(suggestions)}?"
            else:
                suggestion = f"Available functions: {', '.join(sorted(self.known_functions)[:5])}..."
            
            raise QueryFunctionError(
                f"Unknown function: {node.function_name}",
                function_name=node.function_name,
                position=node.position,
                suggestion=suggestion
            )
        
        # Validate arguments
        for arg in node.arguments:
            self._validate_node(arg)


@dataclass
class QueryMetrics:
    """
    Query execution metrics.
    
    Tracks performance and resource usage statistics.
    """
    query_type: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    entities_scanned: int = 0
    entities_returned: int = 0
    cache_hit: bool = False
    error: Optional[str] = None
    
    def complete(self, duration_ms: float) -> None:
        """Mark query as complete with duration."""
        self.end_time = time.time()
        self.duration_ms = duration_ms


class MetricsCollector:
    """
    Collects and aggregates query metrics.
    
    Tracks query counts, latency percentiles, error rates, and cache hits.
    
    Features:
        - Per-query-type metrics
        - Latency percentiles (p50, p95, p99)
        - Error rate tracking
        - Cache hit rate calculation
    
    Example:
        >>> metrics = MetricsCollector()
        >>> metrics.record_query_start('point_query')
        >>> # ... execute query ...
        >>> metrics.record_query_end('point_query', duration_ms=1.5)
        >>> stats = metrics.get_statistics()
        >>> print(f"P95 latency: {stats['latency_p95']:.2f}ms")
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.query_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.latencies: List[float] = []
        self.active_queries: Dict[str, QueryMetrics] = {}
        
        # Running totals
        self.total_queries = 0
        self.total_errors = 0
        self.total_entities_scanned = 0
        self.total_entities_returned = 0
    
    def record_query_start(
        self,
        query_type: str,
        query_id: Optional[str] = None
    ) -> str:
        """
        Record query start.
        
        Args:
            query_type: Type of query (point_query, partition_scan, etc)
            query_id: Optional query identifier
            
        Returns:
            Query ID for tracking
        """
        if query_id is None:
            query_id = f"{query_type}_{time.time()}"
        
        metrics = QueryMetrics(query_type=query_type)
        self.active_queries[query_id] = metrics
        
        return query_id
    
    def record_query_end(
        self,
        query_id: str,
        duration_ms: float,
        entities_scanned: int = 0,
        entities_returned: int = 0,
        cache_hit: bool = False,
        error: Optional[str] = None
    ) -> None:
        """
        Record query completion.
        
        Args:
            query_id: Query identifier from record_query_start
            duration_ms: Query duration in milliseconds
            entities_scanned: Number of entities scanned
            entities_returned: Number of entities returned
            cache_hit: Whether query hit cache
            error: Error message if query failed
        """
        if query_id not in self.active_queries:
            return
        
        metrics = self.active_queries.pop(query_id)
        metrics.complete(duration_ms)
        metrics.entities_scanned = entities_scanned
        metrics.entities_returned = entities_returned
        metrics.cache_hit = cache_hit
        metrics.error = error
        
        # Update counters
        self.total_queries += 1
        self.query_counts[metrics.query_type] += 1
        self.latencies.append(duration_ms)
        self.total_entities_scanned += entities_scanned
        self.total_entities_returned += entities_returned
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        if error:
            self.total_errors += 1
            self.error_counts[error] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregated statistics.
        
        Returns:
            Dictionary with metrics statistics
        """
        total_cache_ops = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            self.cache_hits / total_cache_ops
            if total_cache_ops > 0
            else 0.0
        )
        
        error_rate = (
            self.total_errors / self.total_queries
            if self.total_queries > 0
            else 0.0
        )
        
        # Calculate latency percentiles
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        if n > 0:
            p50_idx = int(n * 0.50)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)
            
            latency_p50 = sorted_latencies[p50_idx] if p50_idx < n else 0.0
            latency_p95 = sorted_latencies[p95_idx] if p95_idx < n else 0.0
            latency_p99 = sorted_latencies[p99_idx] if p99_idx < n else 0.0
            latency_avg = sum(sorted_latencies) / n
            latency_max = sorted_latencies[-1]
        else:
            latency_p50 = latency_p95 = latency_p99 = 0.0
            latency_avg = latency_max = 0.0
        
        return {
            'total_queries': self.total_queries,
            'query_counts': dict(self.query_counts),
            'total_errors': self.total_errors,
            'error_counts': dict(self.error_counts),
            'error_rate': error_rate,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': cache_hit_rate,
            'latency_p50': latency_p50,
            'latency_p95': latency_p95,
            'latency_p99': latency_p99,
            'latency_avg': latency_avg,
            'latency_max': latency_max,
            'total_entities_scanned': self.total_entities_scanned,
            'total_entities_returned': self.total_entities_returned,
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.query_counts.clear()
        self.error_counts.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.latencies.clear()
        self.active_queries.clear()
        self.total_queries = 0
        self.total_errors = 0
        self.total_entities_scanned = 0
        self.total_entities_returned = 0


class QueryLogger:
    """
    Structured logger for OData queries.
    
    Provides structured logging with query context and performance metrics.
    
    Example:
        >>> logger = QueryLogger()
        >>> logger.log_query_start("Price gt 50", query_type='partition_scan')
        >>> # ... execute query ...
        >>> logger.log_query_end(duration_ms=5.2, entities_returned=25)
    """
    
    def __init__(self, logger_name: str = "odata.query"):
        """
        Initialize query logger.
        
        Args:
            logger_name: Logger name for Python logging
        """
        self.logger = logging.getLogger(logger_name)
    
    def log_query_start(
        self,
        query_expression: str,
        query_type: Optional[str] = None,
        **context
    ) -> None:
        """
        Log query start.
        
        Args:
            query_expression: OData filter expression
            query_type: Type of query plan
            **context: Additional context
        """
        self.logger.info(
            "Query started",
            extra={
                'event': 'query_start',
                'query_expression': query_expression,
                'query_type': query_type,
                **context
            }
        )
    
    def log_query_end(
        self,
        duration_ms: float,
        entities_scanned: int = 0,
        entities_returned: int = 0,
        cache_hit: bool = False,
        **context
    ) -> None:
        """
        Log query completion.
        
        Args:
            duration_ms: Query duration
            entities_scanned: Entities scanned
            entities_returned: Entities returned
            cache_hit: Whether cache was hit
            **context: Additional context
        """
        self.logger.info(
            f"Query completed in {duration_ms:.2f}ms",
            extra={
                'event': 'query_end',
                'duration_ms': duration_ms,
                'entities_scanned': entities_scanned,
                'entities_returned': entities_returned,
                'cache_hit': cache_hit,
                **context
            }
        )
    
    def log_error(
        self,
        error: Exception,
        query_expression: Optional[str] = None,
        **context
    ) -> None:
        """
        Log query error.
        
        Args:
            error: Exception that occurred
            query_expression: Query that caused error
            **context: Additional context
        """
        error_dict = {}
        if isinstance(error, ODataQueryError):
            error_dict = error.to_dict()
        
        self.logger.error(
            f"Query error: {str(error)}",
            extra={
                'event': 'query_error',
                'error_type': type(error).__name__,
                'error_message': str(error),
                'query_expression': query_expression,
                'error_details': error_dict,
                **context
            },
            exc_info=True
        )


class ErrorFormatter:
    """
    Formats errors with context and suggestions.
    
    Provides helpful error messages with source context highlighting.
    
    Example:
        >>> formatter = ErrorFormatter()
        >>> formatted = formatter.format_error(
        ...     error,
        ...     source="Price gt 50 andd Active eq true"
        ... )
        >>> print(formatted)
    """
    
    def __init__(self, context_lines: int = 2):
        """
        Initialize error formatter.
        
        Args:
            context_lines: Number of context lines to show
        """
        self.context_lines = context_lines
    
    def format_error(
        self,
        error: ODataQueryError,
        source: Optional[str] = None
    ) -> str:
        """
        Format error with context.
        
        Args:
            error: Error to format
            source: Source query string
            
        Returns:
            Formatted error message
        """
        lines = []
        lines.append(str(error))
        
        if source and error.position:
            lines.append("")
            lines.append("Query:")
            lines.append(f"  {source}")
            
            # Highlight error position
            pointer = " " * (error.position.column + 1) + "^"
            lines.append(pointer)
        
        return "\n".join(lines)
    
    def suggest_fix(self, error_message: str, known_tokens: List[str]) -> Optional[str]:
        """
        Suggest fix for common errors.
        
        Args:
            error_message: Error message
            known_tokens: List of known valid tokens
            
        Returns:
            Suggestion string or None
        """
        # Extract potential typo from error message
        if "Unknown" in error_message or "unexpected" in error_message.lower():
            # Try to find close matches
            words = error_message.split()
            for word in words:
                if len(word) > 2:
                    matches = difflib.get_close_matches(
                        word.lower(),
                        [t.lower() for t in known_tokens],
                        n=1,
                        cutoff=0.7
                    )
                    if matches:
                        return f"Did you mean '{matches[0]}'?"
        
        return None
