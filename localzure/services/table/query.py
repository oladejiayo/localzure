"""
OData query parser and filter engine for Table Storage.

Supports $filter, $select, $top query parameters with OData operators.
"""

from typing import Any, Dict, List, Optional, Callable
import re
from datetime import datetime


class ODataParseError(Exception):
    """Raised when OData expression parsing fails."""
    pass


class ODataFilter:
    """
    OData filter expression parser and evaluator.
    
    Supports:
    - Comparison operators: eq, ne, gt, ge, lt, le
    - Logical operators: and, or, not
    - String functions: startswith, endswith, contains (limited)
    """
    
    # Operator mappings
    COMPARISON_OPS = {
        'eq': lambda a, b: a == b,
        'ne': lambda a, b: a != b,
        'gt': lambda a, b: a > b,
        'ge': lambda a, b: a >= b,
        'lt': lambda a, b: a < b,
        'le': lambda a, b: a <= b,
    }
    
    STRING_FUNCS = {
        'startswith': lambda s, prefix: isinstance(s, str) and s.startswith(prefix),
        'endswith': lambda s, suffix: isinstance(s, str) and s.endswith(suffix),
        'contains': lambda s, substr: isinstance(s, str) and substr in s,
    }
    
    def __init__(self, filter_expr: str):
        """
        Initialize OData filter.
        
        Args:
            filter_expr: OData filter expression
        """
        self.filter_expr = filter_expr.strip()
        self.tokens = self._tokenize(self.filter_expr)
        self.pos = 0
        self._parsed_func = None  # Cache parsed function
    
    def _tokenize(self, expr: str) -> List[str]:
        """
        Tokenize filter expression.
        
        Args:
            expr: Filter expression string
            
        Returns:
            List of tokens
        """
        # Handle quoted strings, numbers (including decimals), operators, identifiers, and parentheses
        pattern = r"'[^']*'|\d+\.\d+|\d+|[(),]|(?:eq|ne|gt|ge|lt|le|and|or|not|true|false|startswith|endswith|contains)\b|\w+"
        tokens = re.findall(pattern, expr, re.IGNORECASE)
        return tokens
    
    def _current_token(self) -> Optional[str]:
        """Get current token without consuming."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None
    
    def _consume_token(self) -> Optional[str]:
        """Consume and return current token."""
        token = self._current_token()
        if token:
            self.pos += 1
        return token
    
    def _parse_value(self, value_str: str) -> Any:
        """
        Parse value from string.
        
        Args:
            value_str: Value string
            
        Returns:
            Parsed value (str, int, float, bool, datetime)
        """
        # Remove quotes for string literals
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        
        # Try parsing as number
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass
        
        # Try boolean
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
        
        # Try datetime (ISO format)
        try:
            return datetime.fromisoformat(value_str.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        # Return as-is (property name)
        return value_str
    
    def _parse_primary(self) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse primary expression (comparison, string function, or parenthesized expression).
        
        Returns:
            Evaluation function
        """
        token = self._current_token()
        
        if token is None:
            raise ODataParseError("Unexpected end of expression")
        
        # Handle parentheses
        if token == '(':
            self._consume_token()  # consume '('
            expr = self._parse_or()
            if self._consume_token() != ')':
                raise ODataParseError("Expected closing parenthesis")
            return expr
        
        # Handle 'not' operator
        if token.lower() == 'not':
            self._consume_token()
            sub_expr = self._parse_primary()
            return lambda entity: not sub_expr(entity)
        
        # Check for string functions
        next_token = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
        if next_token == '(':
            func_name = self._consume_token().lower()
            if func_name in self.STRING_FUNCS:
                return self._parse_string_function(func_name)
        
        # Parse comparison expression
        return self._parse_comparison()
    
    def _parse_string_function(self, func_name: str) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse string function call.
        
        Args:
            func_name: Function name (startswith, endswith, contains)
            
        Returns:
            Evaluation function
        """
        self._consume_token()  # consume '('
        
        prop_name = self._consume_token()
        if self._consume_token() != ',':
            raise ODataParseError(f"Expected comma in {func_name} function")
        
        value_token = self._consume_token()
        value = self._parse_value(value_token)
        
        if self._consume_token() != ')':
            raise ODataParseError(f"Expected closing parenthesis in {func_name} function")
        
        func = self.STRING_FUNCS[func_name]
        return lambda entity: func(entity.get(prop_name), value)
    
    def _parse_comparison(self) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse comparison expression.
        
        Returns:
            Evaluation function
        """
        left_token = self._consume_token()
        if left_token is None:
            raise ODataParseError("Expected property name")
        
        op_token = self._consume_token()
        if op_token is None:
            raise ODataParseError("Expected comparison operator")
        
        op = op_token.lower()
        if op not in self.COMPARISON_OPS:
            raise ODataParseError(f"Unknown comparison operator: {op}")
        
        right_token = self._consume_token()
        if right_token is None:
            raise ODataParseError("Expected value")
        
        left_value = self._parse_value(left_token)
        right_value = self._parse_value(right_token)
        comparison_func = self.COMPARISON_OPS[op]
        
        # Build evaluation function
        def evaluate(entity: Dict[str, Any]) -> bool:
            # Resolve property names
            left_eval = entity.get(left_value, left_value) if isinstance(left_value, str) else left_value
            right_eval = entity.get(right_value, right_value) if isinstance(right_value, str) else right_value
            
            try:
                return comparison_func(left_eval, right_eval)
            except (TypeError, AttributeError):
                return False
        
        return evaluate
    
    def _parse_and(self) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse AND expression.
        
        Returns:
            Evaluation function
        """
        left = self._parse_primary()
        
        while self._current_token() and self._current_token().lower() == 'and':
            self._consume_token()  # consume 'and'
            right = self._parse_primary()
            left = lambda entity, l=left, r=right: l(entity) and r(entity)
        
        return left
    
    def _parse_or(self) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse OR expression.
        
        Returns:
            Evaluation function
        """
        left = self._parse_and()
        
        while self._current_token() and self._current_token().lower() == 'or':
            self._consume_token()  # consume 'or'
            right = self._parse_and()
            left = lambda entity, l=left, r=right: l(entity) or r(entity)
        
        return left
    
    def parse(self) -> Callable[[Dict[str, Any]], bool]:
        """
        Parse the complete filter expression.
        
        Returns:
            Evaluation function that takes entity dict and returns bool
        """
        if not self.filter_expr:
            return lambda entity: True
        
        # Reset position for fresh parse
        self.pos = 0
        
        result = self._parse_or()
        
        if self.pos < len(self.tokens):
            raise ODataParseError(f"Unexpected token: {self.tokens[self.pos]}")
        
        return result
    
    def evaluate(self, entity: Dict[str, Any]) -> bool:
        """
        Evaluate filter against entity.
        
        Args:
            entity: Entity as dictionary
            
        Returns:
            True if entity matches filter
        """
        if self._parsed_func is None:
            self._parsed_func = self.parse()
        return self._parsed_func(entity)


class ODataQuery:
    """
    OData query parser for Table Storage queries.
    
    Supports $filter, $select, $top parameters.
    """
    
    def __init__(
        self,
        filter_expr: Optional[str] = None,
        select: Optional[str] = None,
        top: Optional[int] = None
    ):
        """
        Initialize OData query.
        
        Args:
            filter_expr: $filter expression
            select: $select comma-separated properties
            top: $top result limit
        """
        self.filter = ODataFilter(filter_expr) if filter_expr else None
        self.select_props = [p.strip() for p in select.split(',')] if select else None
        self.top = top
    
    def matches(self, entity: Dict[str, Any]) -> bool:
        """
        Check if entity matches filter.
        
        Args:
            entity: Entity as dictionary
            
        Returns:
            True if entity matches filter (or no filter specified)
        """
        if self.filter is None:
            return True
        return self.filter.evaluate(entity)
    
    def project(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Project entity to selected properties.
        
        Args:
            entity: Entity as dictionary
            
        Returns:
            Projected entity (or original if no $select)
        """
        if self.select_props is None:
            return entity
        
        # Always include system properties
        result = {}
        system_props = {'PartitionKey', 'RowKey', 'Timestamp', 'odata.etag', 'etag'}
        
        for key, value in entity.items():
            if key in system_props or key in self.select_props:
                result[key] = value
        
        return result
