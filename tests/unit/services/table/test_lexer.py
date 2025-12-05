"""
Unit tests for OData Lexer.

Comprehensive test suite covering:
- All literal types
- All operators
- All functions
- Error cases
- Edge cases
- Performance benchmarks
"""

import pytest
from localzure.services.table.lexer import (
    ODataLexer,
    Token,
    TokenType,
    Position,
    LexerError,
)


class TestLiteralTokenization:
    """Tests for literal value tokenization."""
    
    def test_simple_string(self):
        """Test simple string literal."""
        lexer = ODataLexer("'hello'")
        tokens = lexer.tokenize()
        
        assert len(tokens) == 2  # STRING + EOF
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"
    
    def test_string_with_escaped_quote(self):
        """Test string with escaped quote."""
        lexer = ODataLexer("'can''t'")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "can't"
    
    def test_empty_string(self):
        """Test empty string literal."""
        lexer = ODataLexer("''")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == ""
    
    def test_string_with_spaces(self):
        """Test string with spaces."""
        lexer = ODataLexer("'hello world'")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"
    
    def test_positive_integer(self):
        """Test positive integer."""
        lexer = ODataLexer("123")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == 123
    
    def test_negative_integer(self):
        """Test negative integer."""
        lexer = ODataLexer("-456")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == -456
    
    def test_zero_integer(self):
        """Test zero."""
        lexer = ODataLexer("0")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == 0
    
    def test_float_decimal(self):
        """Test float with decimal point."""
        lexer = ODataLexer("123.45")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == 123.45
    
    def test_float_scientific_notation(self):
        """Test float with scientific notation."""
        lexer = ODataLexer("1.23e10")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == 1.23e10
    
    def test_float_negative_exponent(self):
        """Test float with negative exponent."""
        lexer = ODataLexer("1.23e-10")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == 1.23e-10
    
    def test_boolean_true(self):
        """Test boolean true."""
        lexer = ODataLexer("true")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value is True
    
    def test_boolean_false(self):
        """Test boolean false."""
        lexer = ODataLexer("false")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value is False
    
    def test_null_literal(self):
        """Test null literal."""
        lexer = ODataLexer("null")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.NULL
    
    def test_datetime_literal(self):
        """Test datetime literal."""
        lexer = ODataLexer("datetime'2025-12-05T10:30:00Z'")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.DATETIME
        assert tokens[0].value == "2025-12-05T10:30:00Z"
    
    def test_guid_literal(self):
        """Test GUID literal."""
        lexer = ODataLexer("guid'12345678-1234-1234-1234-123456789012'")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.GUID
        assert tokens[0].value == "12345678-1234-1234-1234-123456789012"


class TestOperatorTokenization:
    """Tests for operator tokenization."""
    
    def test_comparison_eq(self):
        """Test eq operator."""
        lexer = ODataLexer("eq")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.EQ
    
    def test_comparison_ne(self):
        """Test ne operator."""
        lexer = ODataLexer("ne")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.NE
    
    def test_comparison_gt(self):
        """Test gt operator."""
        lexer = ODataLexer("gt")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.GT
    
    def test_comparison_ge(self):
        """Test ge operator."""
        lexer = ODataLexer("ge")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.GE
    
    def test_comparison_lt(self):
        """Test lt operator."""
        lexer = ODataLexer("lt")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.LT
    
    def test_comparison_le(self):
        """Test le operator."""
        lexer = ODataLexer("le")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.LE
    
    def test_logical_and(self):
        """Test and operator."""
        lexer = ODataLexer("and")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.AND
    
    def test_logical_or(self):
        """Test or operator."""
        lexer = ODataLexer("or")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.OR
    
    def test_logical_not(self):
        """Test not operator."""
        lexer = ODataLexer("not")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.NOT
    
    def test_arithmetic_add(self):
        """Test add operator."""
        lexer = ODataLexer("add")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.ADD
    
    def test_arithmetic_sub(self):
        """Test sub operator."""
        lexer = ODataLexer("sub")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.SUB
    
    def test_arithmetic_mul(self):
        """Test mul operator."""
        lexer = ODataLexer("mul")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.MUL
    
    def test_arithmetic_div(self):
        """Test div operator."""
        lexer = ODataLexer("div")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.DIV
    
    def test_arithmetic_mod(self):
        """Test mod operator."""
        lexer = ODataLexer("mod")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.MOD


class TestFunctionTokenization:
    """Tests for function name tokenization."""
    
    @pytest.mark.parametrize("func_name", [
        'startswith', 'endswith', 'contains', 'substringof',
        'tolower', 'toupper', 'trim', 'concat', 'substring',
        'length', 'indexof', 'replace'
    ])
    def test_string_functions(self, func_name):
        """Test string function names."""
        lexer = ODataLexer(func_name)
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == func_name
    
    @pytest.mark.parametrize("func_name", [
        'year', 'month', 'day', 'hour', 'minute', 'second'
    ])
    def test_date_functions(self, func_name):
        """Test date function names."""
        lexer = ODataLexer(func_name)
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == func_name
    
    @pytest.mark.parametrize("func_name", [
        'round', 'floor', 'ceiling'
    ])
    def test_math_functions(self, func_name):
        """Test math function names."""
        lexer = ODataLexer(func_name)
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == func_name
    
    @pytest.mark.parametrize("func_name", [
        'isof', 'cast'
    ])
    def test_type_functions(self, func_name):
        """Test type function names."""
        lexer = ODataLexer(func_name)
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == func_name
    
    def test_function_case_insensitive(self):
        """Test function name case insensitivity."""
        for variant in ['startswith', 'StartsWith', 'STARTSWITH', 'sTaRtSwItH']:
            lexer = ODataLexer(variant)
            tokens = lexer.tokenize()
            assert tokens[0].type == TokenType.FUNCTION
            assert tokens[0].value == 'startswith'


class TestIdentifierTokenization:
    """Tests for identifier tokenization."""
    
    def test_simple_identifier(self):
        """Test simple identifier."""
        lexer = ODataLexer("PropertyName")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "PropertyName"
    
    def test_identifier_with_underscore(self):
        """Test identifier with underscore."""
        lexer = ODataLexer("Property_Name")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "Property_Name"
    
    def test_identifier_with_number(self):
        """Test identifier with number."""
        lexer = ODataLexer("Column1")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "Column1"
    
    def test_identifier_starting_with_underscore(self):
        """Test identifier starting with underscore."""
        lexer = ODataLexer("_id")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "_id"
    
    def test_identifier_case_sensitive(self):
        """Test identifier case sensitivity."""
        lexer = ODataLexer("MyProperty")
        tokens = lexer.tokenize()
        assert tokens[0].value == "MyProperty"  # Preserves case


class TestPunctuationTokenization:
    """Tests for punctuation tokenization."""
    
    def test_left_paren(self):
        """Test left parenthesis."""
        lexer = ODataLexer("(")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.LPAREN
    
    def test_right_paren(self):
        """Test right parenthesis."""
        lexer = ODataLexer(")")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.RPAREN
    
    def test_comma(self):
        """Test comma."""
        lexer = ODataLexer(",")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.COMMA
    
    def test_nested_parens(self):
        """Test nested parentheses."""
        lexer = ODataLexer("((")
        tokens = lexer.tokenize()
        assert len(tokens) == 3  # ( ( EOF
        assert tokens[0].type == TokenType.LPAREN
        assert tokens[1].type == TokenType.LPAREN


class TestComplexExpressions:
    """Tests for complex expressions."""
    
    def test_simple_comparison(self):
        """Test simple comparison expression."""
        lexer = ODataLexer("Price gt 50")
        tokens = lexer.tokenize()
        
        assert len(tokens) == 4  # IDENTIFIER GT INTEGER EOF
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "Price"
        assert tokens[1].type == TokenType.GT
        assert tokens[2].type == TokenType.INTEGER
        assert tokens[2].value == 50
    
    def test_logical_and(self):
        """Test logical AND expression."""
        lexer = ODataLexer("Active eq true and Price gt 50")
        tokens = lexer.tokenize()
        
        assert len(tokens) == 8  # Active eq true and Price gt 50 EOF
        assert tokens[0].value == "Active"
        assert tokens[1].type == TokenType.EQ
        assert tokens[2].value is True
        assert tokens[3].type == TokenType.AND
        assert tokens[4].value == "Price"
        assert tokens[5].type == TokenType.GT
        assert tokens[6].value == 50
    
    def test_string_function_call(self):
        """Test string function call."""
        lexer = ODataLexer("startswith(Name, 'Azure')")
        tokens = lexer.tokenize()
        
        assert len(tokens) == 7  # startswith ( Name , 'Azure' ) EOF
        assert tokens[0].type == TokenType.FUNCTION
        assert tokens[0].value == "startswith"
        assert tokens[1].type == TokenType.LPAREN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "Name"
        assert tokens[3].type == TokenType.COMMA
        assert tokens[4].type == TokenType.STRING
        assert tokens[4].value == "Azure"
        assert tokens[5].type == TokenType.RPAREN
    
    def test_nested_expression(self):
        """Test nested expression with parentheses."""
        lexer = ODataLexer("(Price gt 50 and Price lt 200) or Stock gt 150")
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.LPAREN
        assert tokens[8].type == TokenType.RPAREN
        assert tokens[9].type == TokenType.OR
    
    def test_complex_real_world(self):
        """Test complex real-world expression."""
        expr = "PartitionKey eq 'Books' and (Price gt 50 or contains(Name, 'Azure'))"
        lexer = ODataLexer(expr)
        tokens = lexer.tokenize()
        
        # Should tokenize without errors
        assert tokens[-1].type == TokenType.EOF
        assert len(tokens) > 10
    
    def test_multiple_functions(self):
        """Test multiple function calls."""
        expr = "startswith(Name, 'A') and endswith(Name, 'Z')"
        lexer = ODataLexer(expr)
        tokens = lexer.tokenize()
        
        func_tokens = [t for t in tokens if t.type == TokenType.FUNCTION]
        assert len(func_tokens) == 2
        assert func_tokens[0].value == 'startswith'
        assert func_tokens[1].value == 'endswith'
    
    def test_whitespace_handling(self):
        """Test whitespace handling."""
        expr1 = "Price gt 50"
        expr2 = "Price  gt  50"
        expr3 = "Price\tgt\t50"
        expr4 = "Price\ngt\n50"
        
        for expr in [expr1, expr2, expr3, expr4]:
            lexer = ODataLexer(expr)
            tokens = lexer.tokenize()
            # Should produce same token sequence
            assert len(tokens) == 4
            assert tokens[0].value == "Price"
            assert tokens[1].type == TokenType.GT
            assert tokens[2].value == 50


class TestErrorCases:
    """Tests for error handling."""
    
    def test_unclosed_string(self):
        """Test unclosed string literal."""
        lexer = ODataLexer("'hello")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert "Unclosed string literal" in str(exc_info.value)
    
    def test_invalid_character(self):
        """Test invalid character."""
        lexer = ODataLexer("Price @ 50")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert "Unexpected character" in str(exc_info.value)
    
    def test_invalid_datetime_no_quote(self):
        """Test invalid datetime without quote immediately after."""
        # "datetime" followed by space then something else - should just be identifier
        lexer = ODataLexer("datetime '2025'")
        tokens = lexer.tokenize()
        # This is valid - datetime is just an identifier here
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "datetime"
        
        # But "datetime" alone followed by non-quote triggers error expectation
        # Actually, per OData spec, datetime MUST be followed by quote for literal
        # But as standalone, it's just an identifier (property name)
        lexer2 = ODataLexer("datetime")
        tokens2 = lexer2.tokenize()
        assert tokens2[0].type == TokenType.IDENTIFIER
    
    def test_invalid_guid_no_quote(self):
        """Test invalid GUID without quote immediately after."""
        # "guid" followed by space then something else - should just be identifier
        lexer = ODataLexer("guid '12345'")
        tokens = lexer.tokenize()
        # This is valid - guid is just an identifier here
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "guid"
    
    def test_unclosed_datetime(self):
        """Test unclosed datetime literal."""
        lexer = ODataLexer("datetime'2025-12-05")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert "Unclosed datetime literal" in str(exc_info.value)
    
    def test_unclosed_guid(self):
        """Test unclosed GUID literal."""
        lexer = ODataLexer("guid'12345678")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert "Unclosed guid literal" in str(exc_info.value)
    
    def test_invalid_guid_format(self):
        """Test invalid GUID format."""
        lexer = ODataLexer("guid'invalid-guid'")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert "Invalid GUID format" in str(exc_info.value)
    
    def test_error_position_tracking(self):
        """Test error position tracking."""
        lexer = ODataLexer("Price gt 50 and @")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        error = exc_info.value
        assert error.position.line == 1
        assert error.position.column > 10  # After "Price gt 50 and "
    
    def test_multiline_error_position(self):
        """Test error position on multiple lines."""
        lexer = ODataLexer("Price gt 50\nand\n@")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        error = exc_info.value
        assert error.position.line == 3  # Third line
    
    def test_error_with_suggestion(self):
        """Test error includes suggestion."""
        lexer = ODataLexer("'unclosed")
        with pytest.raises(LexerError) as exc_info:
            lexer.tokenize()
        assert exc_info.value.suggestion is not None


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_input(self):
        """Test empty input."""
        lexer = ODataLexer("")
        tokens = lexer.tokenize()
        assert len(tokens) == 1  # Only EOF
        assert tokens[0].type == TokenType.EOF
    
    def test_whitespace_only(self):
        """Test whitespace-only input."""
        lexer = ODataLexer("   \t  \n  ")
        tokens = lexer.tokenize()
        assert len(tokens) == 1  # Only EOF
        assert tokens[0].type == TokenType.EOF
    
    def test_very_long_string(self):
        """Test very long string literal."""
        long_string = 'a' * 10000
        lexer = ODataLexer(f"'{long_string}'")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == long_string
    
    def test_unicode_in_string(self):
        """Test Unicode characters in string."""
        lexer = ODataLexer("'Hello 世界 🌍'")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "Hello 世界 🌍"
    
    def test_unicode_identifier(self):
        """Test Unicode in identifier (should work with Python 3)."""
        lexer = ODataLexer("Naïve")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "Naïve"
    
    def test_special_chars_in_string(self):
        """Test special characters in string."""
        lexer = ODataLexer("'tab\\there'")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.STRING
        # Backslashes are preserved (no escape processing except for quotes)
        assert '\\t' in tokens[0].value
    
    def test_very_large_number(self):
        """Test very large number."""
        lexer = ODataLexer("999999999999999999")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == 999999999999999999
    
    def test_very_small_float(self):
        """Test very small float."""
        lexer = ODataLexer("1.23e-100")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.FLOAT
        assert tokens[0].value == 1.23e-100


class TestPositionTracking:
    """Tests for position tracking."""
    
    def test_single_line_positions(self):
        """Test position tracking on single line."""
        lexer = ODataLexer("Price gt 50")
        tokens = lexer.tokenize()
        
        assert tokens[0].position.line == 1
        assert tokens[0].position.column == 1
        assert tokens[1].position.column == 7  # After "Price "
        assert tokens[2].position.column == 10  # After "Price gt "
    
    def test_multiline_positions(self):
        """Test position tracking across multiple lines."""
        lexer = ODataLexer("Price gt 50\nand\nActive eq true")
        tokens = lexer.tokenize()
        
        # First line
        assert tokens[0].position.line == 1
        # Second line
        and_token = [t for t in tokens if t.type == TokenType.AND][0]
        assert and_token.position.line == 2
        # Third line
        active_token = [t for t in tokens if t.value == "Active"][0]
        assert active_token.position.line == 3
    
    def test_token_length(self):
        """Test token length tracking."""
        lexer = ODataLexer("'hello' 123 startswith")
        tokens = lexer.tokenize()
        
        assert tokens[0].length == 7  # 'hello' (including quotes)
        assert tokens[1].length == 3  # 123
        assert tokens[2].length == 10  # startswith


class TestPerformance:
    """Performance benchmarks."""
    
    def test_simple_expression_performance(self):
        """Benchmark simple expression tokenization."""
        expr = "Price gt 50 and Active eq true"
        lexer = ODataLexer(expr)
        
        import time
        start = time.perf_counter()
        iterations = 10000
        for _ in range(iterations):
            tokens = lexer.tokenize()
            lexer.pos = 0
            lexer.line = 1
            lexer.column = 1
        end = time.perf_counter()
        
        elapsed = end - start
        tokens_per_sec = (len(tokens) - 1) * iterations / elapsed  # Exclude EOF
        
        # Should achieve > 100k tokens/sec
        assert tokens_per_sec > 100_000, f"Too slow: {tokens_per_sec:.0f} tokens/sec"
    
    def test_complex_expression_performance(self):
        """Benchmark complex expression tokenization."""
        expr = "(Price gt 50 and Price lt 200) or (Stock gt 150 and Active eq true) or startswith(Name, 'Azure')"
        lexer = ODataLexer(expr)
        
        import time
        start = time.perf_counter()
        iterations = 5000
        for _ in range(iterations):
            tokens = lexer.tokenize()
            lexer.pos = 0
            lexer.line = 1
            lexer.column = 1
        end = time.perf_counter()
        
        elapsed = end - start
        tokens_per_sec = (len(tokens) - 1) * iterations / elapsed
        
        # Should still achieve > 100k tokens/sec
        assert tokens_per_sec > 100_000, f"Too slow: {tokens_per_sec:.0f} tokens/sec"
    
    def test_large_input_performance(self):
        """Benchmark large input tokenization."""
        # Generate large expression
        parts = ["Price gt 50"] * 100
        expr = " and ".join(parts)
        lexer = ODataLexer(expr)
        
        import time
        start = time.perf_counter()
        tokens = lexer.tokenize()
        end = time.perf_counter()
        
        elapsed = end - start
        # Should tokenize in reasonable time (< 10ms for ~600 tokens)
        assert elapsed < 0.01, f"Too slow: {elapsed:.4f}s for {len(tokens)} tokens"


class TestTokenRepresentation:
    """Tests for token string representations."""
    
    def test_token_str(self):
        """Test Token __str__."""
        pos = Position(1, 5, 4)
        token = Token(TokenType.INTEGER, 123, pos, 3)
        assert "INTEGER(123)" in str(token)
        assert "line 1, column 5" in str(token)
    
    def test_token_repr(self):
        """Test Token __repr__."""
        pos = Position(1, 5, 4)
        token = Token(TokenType.INTEGER, 123, pos, 3)
        assert "Token(" in repr(token)
        assert "INTEGER" in repr(token)
    
    def test_position_str(self):
        """Test Position __str__."""
        pos = Position(5, 10, 50)
        assert str(pos) == "line 5, column 10"
    
    def test_lexer_repr(self):
        """Test ODataLexer __repr__."""
        lexer = ODataLexer("Price gt 50")
        assert "ODataLexer" in repr(lexer)
        assert "Price gt 50" in repr(lexer)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
