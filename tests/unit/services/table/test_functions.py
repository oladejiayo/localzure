"""
Tests for OData Function Library.

Comprehensive test coverage for all OData v3 functions including
string, date, math, and type functions.
"""

import pytest
from datetime import datetime

from localzure.services.table.functions import (
    FunctionLibrary,
    FunctionRegistry,
    FunctionSignature,
)
from localzure.services.table.types import EdmType, TypeError as EdmTypeError


class TestStringFunctions:
    """Test string manipulation functions."""
    
    def test_startswith_true(self):
        """Test startswith when prefix matches."""
        assert FunctionLibrary.startswith("HelloWorld", "Hello") is True
        assert FunctionLibrary.startswith("HelloWorld", "hello") is True  # Case-insensitive
        assert FunctionLibrary.startswith("HelloWorld", "HELLO") is True
    
    def test_startswith_false(self):
        """Test startswith when prefix doesn't match."""
        assert FunctionLibrary.startswith("HelloWorld", "World") is False
        assert FunctionLibrary.startswith("HelloWorld", "xyz") is False
    
    def test_startswith_null(self):
        """Test startswith with null inputs."""
        assert FunctionLibrary.startswith(None, "Hello") is None
        assert FunctionLibrary.startswith("Hello", None) is None
        assert FunctionLibrary.startswith(None, None) is None
    
    def test_endswith_true(self):
        """Test endswith when suffix matches."""
        assert FunctionLibrary.endswith("HelloWorld", "World") is True
        assert FunctionLibrary.endswith("HelloWorld", "world") is True  # Case-insensitive
        assert FunctionLibrary.endswith("HelloWorld", "WORLD") is True
    
    def test_endswith_false(self):
        """Test endswith when suffix doesn't match."""
        assert FunctionLibrary.endswith("HelloWorld", "Hello") is False
        assert FunctionLibrary.endswith("HelloWorld", "xyz") is False
    
    def test_endswith_null(self):
        """Test endswith with null inputs."""
        assert FunctionLibrary.endswith(None, "World") is None
        assert FunctionLibrary.endswith("World", None) is None
    
    def test_contains_true(self):
        """Test contains when substring is found."""
        assert FunctionLibrary.contains("HelloWorld", "low") is True  # Case-insensitive
        assert FunctionLibrary.contains("HelloWorld", "World") is True
        assert FunctionLibrary.contains("HelloWorld", "HELLO") is True
    
    def test_contains_false(self):
        """Test contains when substring not found."""
        assert FunctionLibrary.contains("HelloWorld", "xyz") is False
        assert FunctionLibrary.contains("HelloWorld", "Bye") is False
    
    def test_contains_null(self):
        """Test contains with null inputs."""
        assert FunctionLibrary.contains(None, "Hello") is None
        assert FunctionLibrary.contains("Hello", None) is None
    
    def test_substringof_true(self):
        """Test substringof (reversed argument order)."""
        assert FunctionLibrary.substringof("low", "HelloWorld") is True  # Case-insensitive
        assert FunctionLibrary.substringof("World", "HelloWorld") is True
        assert FunctionLibrary.substringof("HELLO", "HelloWorld") is True
    
    def test_substringof_false(self):
        """Test substringof when not found."""
        assert FunctionLibrary.substringof("xyz", "HelloWorld") is False
        assert FunctionLibrary.substringof("Bye", "HelloWorld") is False
    
    def test_substringof_null(self):
        """Test substringof with null inputs."""
        assert FunctionLibrary.substringof(None, "Hello") is None
        assert FunctionLibrary.substringof("Hello", None) is None
    
    def test_tolower(self):
        """Test string to lowercase conversion."""
        assert FunctionLibrary.tolower("HelloWorld") == "helloworld"
        assert FunctionLibrary.tolower("HELLO") == "hello"
        assert FunctionLibrary.tolower("hello") == "hello"
        assert FunctionLibrary.tolower("") == ""
    
    def test_tolower_null(self):
        """Test tolower with null."""
        assert FunctionLibrary.tolower(None) is None
    
    def test_toupper(self):
        """Test string to uppercase conversion."""
        assert FunctionLibrary.toupper("HelloWorld") == "HELLOWORLD"
        assert FunctionLibrary.toupper("hello") == "HELLO"
        assert FunctionLibrary.toupper("HELLO") == "HELLO"
        assert FunctionLibrary.toupper("") == ""
    
    def test_toupper_null(self):
        """Test toupper with null."""
        assert FunctionLibrary.toupper(None) is None
    
    def test_trim(self):
        """Test trimming whitespace."""
        assert FunctionLibrary.trim("  hello  ") == "hello"
        assert FunctionLibrary.trim("hello") == "hello"
        assert FunctionLibrary.trim("  hello") == "hello"
        assert FunctionLibrary.trim("hello  ") == "hello"
        assert FunctionLibrary.trim("\t\nhello\t\n") == "hello"
    
    def test_trim_null(self):
        """Test trim with null."""
        assert FunctionLibrary.trim(None) is None
    
    def test_concat(self):
        """Test string concatenation."""
        assert FunctionLibrary.concat("Hello", "World") == "HelloWorld"
        assert FunctionLibrary.concat("", "Hello") == "Hello"
        assert FunctionLibrary.concat("Hello", "") == "Hello"
        assert FunctionLibrary.concat("", "") == ""
    
    def test_concat_null(self):
        """Test concat with null inputs."""
        assert FunctionLibrary.concat(None, "Hello") is None
        assert FunctionLibrary.concat("Hello", None) is None
        assert FunctionLibrary.concat(None, None) is None
    
    def test_substring_two_args(self):
        """Test substring with start position only."""
        assert FunctionLibrary.substring("HelloWorld", 5) == "World"
        assert FunctionLibrary.substring("HelloWorld", 0) == "HelloWorld"
        assert FunctionLibrary.substring("HelloWorld", 10) == ""
    
    def test_substring_three_args(self):
        """Test substring with start and length."""
        assert FunctionLibrary.substring("HelloWorld", 0, 5) == "Hello"
        assert FunctionLibrary.substring("HelloWorld", 5, 5) == "World"
        assert FunctionLibrary.substring("HelloWorld", 3, 4) == "loWo"
        assert FunctionLibrary.substring("HelloWorld", 0, 100) == "HelloWorld"
    
    def test_substring_negative_start(self):
        """Test substring with negative start (treated as 0)."""
        assert FunctionLibrary.substring("HelloWorld", -5) == "HelloWorld"
        assert FunctionLibrary.substring("HelloWorld", -1, 5) == "Hello"
    
    def test_substring_negative_length(self):
        """Test substring with negative length (treated as 0)."""
        assert FunctionLibrary.substring("HelloWorld", 0, -5) == ""
    
    def test_substring_null(self):
        """Test substring with null inputs."""
        assert FunctionLibrary.substring(None, 0) is None
        assert FunctionLibrary.substring("Hello", None) is None
    
    def test_length(self):
        """Test string length."""
        assert FunctionLibrary.length("HelloWorld") == 10
        assert FunctionLibrary.length("") == 0
        assert FunctionLibrary.length("a") == 1
        assert FunctionLibrary.length("  ") == 2
    
    def test_length_null(self):
        """Test length with null."""
        assert FunctionLibrary.length(None) is None
    
    def test_indexof_found(self):
        """Test indexof when substring is found."""
        assert FunctionLibrary.indexof("HelloWorld", "World") == 5
        assert FunctionLibrary.indexof("HelloWorld", "Hello") == 0
        assert FunctionLibrary.indexof("HelloWorld", "o") == 4
    
    def test_indexof_not_found(self):
        """Test indexof when substring not found."""
        assert FunctionLibrary.indexof("HelloWorld", "xyz") == -1
        assert FunctionLibrary.indexof("HelloWorld", "Bye") == -1
    
    def test_indexof_case_sensitive(self):
        """Test indexof is case-sensitive."""
        assert FunctionLibrary.indexof("HelloWorld", "world") == -1
        assert FunctionLibrary.indexof("HelloWorld", "World") == 5
    
    def test_indexof_null(self):
        """Test indexof with null inputs."""
        assert FunctionLibrary.indexof(None, "Hello") is None
        assert FunctionLibrary.indexof("Hello", None) is None
    
    def test_replace(self):
        """Test string replacement."""
        assert FunctionLibrary.replace("HelloWorld", "World", "Azure") == "HelloAzure"
        assert FunctionLibrary.replace("HelloHello", "Hello", "Hi") == "HiHi"
        assert FunctionLibrary.replace("Hello", "xyz", "abc") == "Hello"
    
    def test_replace_case_sensitive(self):
        """Test replace is case-sensitive."""
        assert FunctionLibrary.replace("HelloWorld", "world", "Azure") == "HelloWorld"
        assert FunctionLibrary.replace("HelloWorld", "World", "Azure") == "HelloAzure"
    
    def test_replace_null(self):
        """Test replace with null inputs."""
        assert FunctionLibrary.replace(None, "a", "b") is None
        assert FunctionLibrary.replace("Hello", None, "b") is None
        assert FunctionLibrary.replace("Hello", "a", None) is None


class TestDateFunctions:
    """Test date/time functions."""
    
    def test_year(self):
        """Test extracting year."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.year(dt) == 2025
        
        dt = datetime(1999, 1, 1)
        assert FunctionLibrary.year(dt) == 1999
    
    def test_year_null(self):
        """Test year with null."""
        assert FunctionLibrary.year(None) is None
    
    def test_month(self):
        """Test extracting month."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.month(dt) == 12
        
        dt = datetime(2025, 1, 5)
        assert FunctionLibrary.month(dt) == 1
    
    def test_month_null(self):
        """Test month with null."""
        assert FunctionLibrary.month(None) is None
    
    def test_day(self):
        """Test extracting day."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.day(dt) == 5
        
        dt = datetime(2025, 12, 31)
        assert FunctionLibrary.day(dt) == 31
    
    def test_day_null(self):
        """Test day with null."""
        assert FunctionLibrary.day(None) is None
    
    def test_hour(self):
        """Test extracting hour."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.hour(dt) == 14
        
        dt = datetime(2025, 12, 5, 0, 30, 45)
        assert FunctionLibrary.hour(dt) == 0
    
    def test_hour_null(self):
        """Test hour with null."""
        assert FunctionLibrary.hour(None) is None
    
    def test_minute(self):
        """Test extracting minute."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.minute(dt) == 30
        
        dt = datetime(2025, 12, 5, 14, 0, 45)
        assert FunctionLibrary.minute(dt) == 0
    
    def test_minute_null(self):
        """Test minute with null."""
        assert FunctionLibrary.minute(None) is None
    
    def test_second(self):
        """Test extracting second."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.second(dt) == 45
        
        dt = datetime(2025, 12, 5, 14, 30, 0)
        assert FunctionLibrary.second(dt) == 0
    
    def test_second_null(self):
        """Test second with null."""
        assert FunctionLibrary.second(None) is None
    
    def test_all_date_components(self):
        """Test extracting all components from same datetime."""
        dt = datetime(2025, 12, 5, 14, 30, 45)
        assert FunctionLibrary.year(dt) == 2025
        assert FunctionLibrary.month(dt) == 12
        assert FunctionLibrary.day(dt) == 5
        assert FunctionLibrary.hour(dt) == 14
        assert FunctionLibrary.minute(dt) == 30
        assert FunctionLibrary.second(dt) == 45


class TestMathFunctions:
    """Test math functions."""
    
    def test_round_positive(self):
        """Test rounding positive numbers."""
        assert FunctionLibrary.round_func(3.7) == 4.0
        assert FunctionLibrary.round_func(3.2) == 3.0
        assert FunctionLibrary.round_func(3.5) == 4.0  # Banker's rounding in Python 3
        assert FunctionLibrary.round_func(2.5) == 2.0
    
    def test_round_negative(self):
        """Test rounding negative numbers."""
        assert FunctionLibrary.round_func(-3.7) == -4.0
        assert FunctionLibrary.round_func(-3.2) == -3.0
    
    def test_round_integer(self):
        """Test rounding integers."""
        assert FunctionLibrary.round_func(5) == 5.0
        assert FunctionLibrary.round_func(0) == 0.0
    
    def test_round_null(self):
        """Test round with null."""
        assert FunctionLibrary.round_func(None) is None
    
    def test_floor_positive(self):
        """Test floor of positive numbers."""
        assert FunctionLibrary.floor(3.7) == 3.0
        assert FunctionLibrary.floor(3.2) == 3.0
        assert FunctionLibrary.floor(3.0) == 3.0
    
    def test_floor_negative(self):
        """Test floor of negative numbers."""
        assert FunctionLibrary.floor(-3.2) == -4.0
        assert FunctionLibrary.floor(-3.7) == -4.0
    
    def test_floor_integer(self):
        """Test floor of integers."""
        assert FunctionLibrary.floor(5) == 5.0
        assert FunctionLibrary.floor(0) == 0.0
    
    def test_floor_null(self):
        """Test floor with null."""
        assert FunctionLibrary.floor(None) is None
    
    def test_ceiling_positive(self):
        """Test ceiling of positive numbers."""
        assert FunctionLibrary.ceiling(3.2) == 4.0
        assert FunctionLibrary.ceiling(3.7) == 4.0
        assert FunctionLibrary.ceiling(3.0) == 3.0
    
    def test_ceiling_negative(self):
        """Test ceiling of negative numbers."""
        assert FunctionLibrary.ceiling(-3.7) == -3.0
        assert FunctionLibrary.ceiling(-3.2) == -3.0
    
    def test_ceiling_integer(self):
        """Test ceiling of integers."""
        assert FunctionLibrary.ceiling(5) == 5.0
        assert FunctionLibrary.ceiling(0) == 0.0
    
    def test_ceiling_null(self):
        """Test ceiling with null."""
        assert FunctionLibrary.ceiling(None) is None


class TestTypeFunctions:
    """Test type checking and casting functions."""
    
    def test_isof_string(self):
        """Test isof for string type."""
        assert FunctionLibrary.isof("hello", "Edm.String") is True
        assert FunctionLibrary.isof(42, "Edm.String") is False
        assert FunctionLibrary.isof(True, "Edm.String") is False
    
    def test_isof_int32(self):
        """Test isof for Int32 type."""
        assert FunctionLibrary.isof(42, "Edm.Int32") is True
        assert FunctionLibrary.isof("42", "Edm.Int32") is False
    
    def test_isof_double(self):
        """Test isof for Double type."""
        assert FunctionLibrary.isof(3.14, "Edm.Double") is True
        assert FunctionLibrary.isof(42, "Edm.Double") is True  # int is numeric
        assert FunctionLibrary.isof("3.14", "Edm.Double") is False
    
    def test_isof_boolean(self):
        """Test isof for Boolean type."""
        assert FunctionLibrary.isof(True, "Edm.Boolean") is True
        assert FunctionLibrary.isof(False, "Edm.Boolean") is True
        assert FunctionLibrary.isof(1, "Edm.Boolean") is False  # int not bool
    
    def test_isof_datetime(self):
        """Test isof for DateTime type."""
        dt = datetime(2025, 12, 5)
        assert FunctionLibrary.isof(dt, "Edm.DateTime") is True
        assert FunctionLibrary.isof("2025-12-05", "Edm.DateTime") is False
    
    def test_isof_null(self):
        """Test isof for null type."""
        assert FunctionLibrary.isof(None, "Edm.Null") is True
        assert FunctionLibrary.isof("", "Edm.Null") is False
        assert FunctionLibrary.isof(0, "Edm.Null") is False
    
    def test_cast_to_string(self):
        """Test casting to string."""
        assert FunctionLibrary.cast(42, "Edm.String") == "42"
        assert FunctionLibrary.cast(3.14, "Edm.String") == "3.14"
        assert FunctionLibrary.cast(True, "Edm.String") == "True"
    
    def test_cast_to_int32(self):
        """Test casting to Int32."""
        assert FunctionLibrary.cast("42", "Edm.Int32") == 42
        assert FunctionLibrary.cast(3.7, "Edm.Int32") == 3
        assert FunctionLibrary.cast(True, "Edm.Int32") == 1
    
    def test_cast_to_double(self):
        """Test casting to Double."""
        assert FunctionLibrary.cast("3.14", "Edm.Double") == 3.14
        assert FunctionLibrary.cast(42, "Edm.Double") == 42.0
    
    def test_cast_to_boolean(self):
        """Test casting to Boolean."""
        assert FunctionLibrary.cast("true", "Edm.Boolean") is True
        assert FunctionLibrary.cast("false", "Edm.Boolean") is False
        assert FunctionLibrary.cast(1, "Edm.Boolean") is True
        assert FunctionLibrary.cast(0, "Edm.Boolean") is False
    
    def test_cast_null(self):
        """Test casting null."""
        assert FunctionLibrary.cast(None, "Edm.String") is None
        assert FunctionLibrary.cast(None, "Edm.Int32") is None
    
    def test_cast_invalid(self):
        """Test invalid casts."""
        with pytest.raises(ValueError):
            FunctionLibrary.cast("hello", "Edm.Int32")
        with pytest.raises(ValueError):
            FunctionLibrary.cast("not a date", "Edm.DateTime")


class TestFunctionRegistry:
    """Test function registry."""
    
    def test_registry_initialization(self):
        """Test registry initializes with all functions."""
        registry = FunctionRegistry()
        functions = registry.list_functions()
        
        # Check we have all expected functions
        assert 'startswith' in functions
        assert 'endswith' in functions
        assert 'contains' in functions
        assert 'tolower' in functions
        assert 'year' in functions
        assert 'round' in functions
        
        # Should have 20+ functions (substring handled specially)
        assert len(functions) >= 20
    
    def test_lookup_function(self):
        """Test looking up functions."""
        registry = FunctionRegistry()
        
        result = registry.lookup('startswith')
        assert result is not None
        func, sig = result
        assert callable(func)
        assert isinstance(sig, FunctionSignature)
    
    def test_lookup_case_insensitive(self):
        """Test function lookup is case-insensitive."""
        registry = FunctionRegistry()
        
        assert registry.lookup('startswith') is not None
        assert registry.lookup('STARTSWITH') is not None
        assert registry.lookup('StartsWith') is not None
    
    def test_lookup_unknown_function(self):
        """Test looking up unknown function."""
        registry = FunctionRegistry()
        assert registry.lookup('unknown_func') is None
    
    def test_call_string_function(self):
        """Test calling string function through registry."""
        registry = FunctionRegistry()
        result = registry.call('startswith', ["HelloWorld", "Hello"])
        assert result is True
    
    def test_call_date_function(self):
        """Test calling date function through registry."""
        registry = FunctionRegistry()
        dt = datetime(2025, 12, 5)
        result = registry.call('year', [dt])
        assert result == 2025
    
    def test_call_math_function(self):
        """Test calling math function through registry."""
        registry = FunctionRegistry()
        result = registry.call('round', [3.7])
        assert result == 4.0
    
    def test_call_substring_two_args(self):
        """Test calling substring with 2 arguments."""
        registry = FunctionRegistry()
        result = registry.call('substring', ["HelloWorld", 5])
        assert result == "World"
    
    def test_call_substring_three_args(self):
        """Test calling substring with 3 arguments."""
        registry = FunctionRegistry()
        result = registry.call('substring', ["HelloWorld", 0, 5])
        assert result == "Hello"
    
    def test_call_wrong_arg_count(self):
        """Test calling function with wrong argument count."""
        registry = FunctionRegistry()
        with pytest.raises(EdmTypeError) as exc:
            registry.call('startswith', ["Hello"])
        assert "expects 2 argument" in str(exc.value)
    
    def test_call_unknown_function(self):
        """Test calling unknown function."""
        registry = FunctionRegistry()
        with pytest.raises(EdmTypeError) as exc:
            registry.call('unknown_func', [])
        assert "Unknown function" in str(exc.value)
    
    def test_get_signature(self):
        """Test getting function signature."""
        registry = FunctionRegistry()
        sig = registry.get_signature('startswith')
        assert sig is not None
        assert len(sig.arg_types) == 2
        assert sig.arg_types[0] == EdmType.STRING
        assert sig.return_type == EdmType.BOOLEAN
    
    def test_get_signature_unknown(self):
        """Test getting signature of unknown function."""
        registry = FunctionRegistry()
        assert registry.get_signature('unknown_func') is None
    
    def test_list_functions(self):
        """Test listing all functions."""
        registry = FunctionRegistry()
        functions = registry.list_functions()
        
        assert isinstance(functions, list)
        assert len(functions) > 0
        assert all(isinstance(name, str) for name in functions)
        # Should be sorted
        assert functions == sorted(functions)


class TestNullPropagation:
    """Test null propagation through functions."""
    
    def test_string_functions_null_propagation(self):
        """Test string functions return None when any arg is None."""
        assert FunctionLibrary.startswith(None, "test") is None
        assert FunctionLibrary.endswith("test", None) is None
        assert FunctionLibrary.contains(None, None) is None
        assert FunctionLibrary.concat(None, "test") is None
        assert FunctionLibrary.substring(None, 0) is None
        assert FunctionLibrary.length(None) is None
    
    def test_date_functions_null_propagation(self):
        """Test date functions return None when arg is None."""
        assert FunctionLibrary.year(None) is None
        assert FunctionLibrary.month(None) is None
        assert FunctionLibrary.day(None) is None
        assert FunctionLibrary.hour(None) is None
        assert FunctionLibrary.minute(None) is None
        assert FunctionLibrary.second(None) is None
    
    def test_math_functions_null_propagation(self):
        """Test math functions return None when arg is None."""
        assert FunctionLibrary.round_func(None) is None
        assert FunctionLibrary.floor(None) is None
        assert FunctionLibrary.ceiling(None) is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_string(self):
        """Test functions with empty strings."""
        assert FunctionLibrary.length("") == 0
        assert FunctionLibrary.startswith("", "") is True
        assert FunctionLibrary.contains("", "") is True
        assert FunctionLibrary.tolower("") == ""
        assert FunctionLibrary.concat("", "") == ""
    
    def test_very_long_string(self):
        """Test functions with very long strings."""
        long_str = "a" * 10000
        assert FunctionLibrary.length(long_str) == 10000
        assert FunctionLibrary.startswith(long_str, "aaa") is True
        assert FunctionLibrary.substring(long_str, 9990) == "a" * 10
    
    def test_unicode_strings(self):
        """Test functions with Unicode characters."""
        unicode_str = "Hello 世界 🌍"
        assert FunctionLibrary.length(unicode_str) == 10
        assert FunctionLibrary.toupper(unicode_str) == "HELLO 世界 🌍"
        assert FunctionLibrary.contains(unicode_str, "世界") is True
    
    def test_special_characters(self):
        """Test functions with special characters."""
        special = "Hello\nWorld\t!"
        assert FunctionLibrary.length(special) == 13
        assert FunctionLibrary.contains(special, "\n") is True
        assert FunctionLibrary.trim("  \t\n  ") == ""
    
    def test_datetime_boundaries(self):
        """Test date functions with boundary values."""
        # Min datetime components
        dt = datetime(1, 1, 1, 0, 0, 0)
        assert FunctionLibrary.year(dt) == 1
        assert FunctionLibrary.month(dt) == 1
        assert FunctionLibrary.day(dt) == 1
        assert FunctionLibrary.hour(dt) == 0
        assert FunctionLibrary.minute(dt) == 0
        assert FunctionLibrary.second(dt) == 0
        
        # Max datetime components
        dt = datetime(9999, 12, 31, 23, 59, 59)
        assert FunctionLibrary.year(dt) == 9999
        assert FunctionLibrary.month(dt) == 12
        assert FunctionLibrary.day(dt) == 31
        assert FunctionLibrary.hour(dt) == 23
        assert FunctionLibrary.minute(dt) == 59
        assert FunctionLibrary.second(dt) == 59
    
    def test_math_with_zero(self):
        """Test math functions with zero."""
        assert FunctionLibrary.round_func(0.0) == 0.0
        assert FunctionLibrary.floor(0.0) == 0.0
        assert FunctionLibrary.ceiling(0.0) == 0.0
    
    def test_math_with_large_numbers(self):
        """Test math functions with large numbers."""
        large = 999999999.999
        assert FunctionLibrary.round_func(large) == 1000000000.0
        assert FunctionLibrary.floor(large) == 999999999.0
        assert FunctionLibrary.ceiling(large) == 1000000000.0
    
    def test_substring_out_of_bounds(self):
        """Test substring with out of bounds indices."""
        s = "Hello"
        # Start beyond end
        assert FunctionLibrary.substring(s, 100) == ""
        # Length beyond end
        assert FunctionLibrary.substring(s, 0, 100) == "Hello"
        # Start at end
        assert FunctionLibrary.substring(s, 5) == ""
    
    def test_indexof_empty_substring(self):
        """Test indexof with empty substring."""
        # Python's behavior: empty string found at position 0
        assert FunctionLibrary.indexof("Hello", "") == 0
    
    def test_replace_empty_string(self):
        """Test replace with empty strings."""
        # Python replaces empty string between every character
        result = FunctionLibrary.replace("Hello", "", "X")
        assert "X" in result  # Will insert X between every char
        # Normal replacement with empty target
        assert FunctionLibrary.replace("Hello", "H", "") == "ello"


class TestCaseSensitivity:
    """Test case sensitivity behavior."""
    
    def test_comparison_functions_case_insensitive(self):
        """Test comparison functions are case-insensitive."""
        assert FunctionLibrary.startswith("HelloWorld", "hello") is True
        assert FunctionLibrary.endswith("HelloWorld", "WORLD") is True
        assert FunctionLibrary.contains("HelloWorld", "LOW") is True
        assert FunctionLibrary.substringof("LOW", "HelloWorld") is True
    
    def test_indexof_case_sensitive(self):
        """Test indexof is case-sensitive."""
        assert FunctionLibrary.indexof("HelloWorld", "World") == 5
        assert FunctionLibrary.indexof("HelloWorld", "world") == -1
    
    def test_replace_case_sensitive(self):
        """Test replace is case-sensitive."""
        assert FunctionLibrary.replace("HelloWorld", "World", "Azure") == "HelloAzure"
        assert FunctionLibrary.replace("HelloWorld", "world", "Azure") == "HelloWorld"
    
    def test_tolower_toupper_inverse(self):
        """Test tolower and toupper are inverses."""
        original = "HelloWorld"
        lower = FunctionLibrary.tolower(original)
        upper = FunctionLibrary.toupper(original)
        
        assert FunctionLibrary.toupper(lower) == "HELLOWORLD"
        assert FunctionLibrary.tolower(upper) == "helloworld"


class TestFunctionSignature:
    """Test function signature class."""
    
    def test_signature_creation(self):
        """Test creating function signatures."""
        sig = FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN)
        assert len(sig.arg_types) == 2
        assert sig.return_type == EdmType.BOOLEAN
        assert sig.allow_numeric_promotion is False
    
    def test_signature_with_promotion(self):
        """Test signature with numeric promotion."""
        sig = FunctionSignature([EdmType.DOUBLE], EdmType.DOUBLE, allow_numeric_promotion=True)
        assert sig.allow_numeric_promotion is True
    
    def test_signature_repr(self):
        """Test signature string representation."""
        sig = FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN)
        repr_str = repr(sig)
        assert "Edm.String" in repr_str
        assert "Edm.Boolean" in repr_str
