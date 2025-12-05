"""
Tests for OData EDM Type System.

Comprehensive test coverage for type inference, validation, compatibility
checking, and conversions.
"""

import pytest
from datetime import datetime
import uuid

from localzure.services.table.types import (
    EdmType,
    TypedValue,
    TypeError as EdmTypeError,
    TypeValidator,
)
from localzure.services.table.lexer import Position


class TestEdmType:
    """Test EDM type enum and methods."""
    
    def test_is_numeric(self):
        """Test numeric type detection."""
        assert EdmType.INT32.is_numeric()
        assert EdmType.INT64.is_numeric()
        assert EdmType.DOUBLE.is_numeric()
        assert not EdmType.STRING.is_numeric()
        assert not EdmType.BOOLEAN.is_numeric()
        assert not EdmType.DATETIME.is_numeric()
    
    def test_is_comparable_same_types(self):
        """Test comparability of same types."""
        assert EdmType.STRING.is_comparable(EdmType.STRING)
        assert EdmType.INT32.is_comparable(EdmType.INT32)
        assert EdmType.BOOLEAN.is_comparable(EdmType.BOOLEAN)
        assert EdmType.DATETIME.is_comparable(EdmType.DATETIME)
    
    def test_is_comparable_numeric_types(self):
        """Test comparability of numeric types."""
        assert EdmType.INT32.is_comparable(EdmType.INT64)
        assert EdmType.INT32.is_comparable(EdmType.DOUBLE)
        assert EdmType.INT64.is_comparable(EdmType.DOUBLE)
        assert EdmType.INT64.is_comparable(EdmType.INT32)
    
    def test_is_comparable_with_null(self):
        """Test that null is comparable with any type."""
        assert EdmType.NULL.is_comparable(EdmType.STRING)
        assert EdmType.NULL.is_comparable(EdmType.INT32)
        assert EdmType.NULL.is_comparable(EdmType.BOOLEAN)
        assert EdmType.STRING.is_comparable(EdmType.NULL)
        assert EdmType.INT32.is_comparable(EdmType.NULL)
    
    def test_is_not_comparable_different_types(self):
        """Test incomparability of different non-numeric types."""
        assert not EdmType.STRING.is_comparable(EdmType.INT32)
        assert not EdmType.STRING.is_comparable(EdmType.BOOLEAN)
        assert not EdmType.BOOLEAN.is_comparable(EdmType.INT32)
        assert not EdmType.DATETIME.is_comparable(EdmType.STRING)
    
    def test_supports_ordering(self):
        """Test ordering support."""
        assert EdmType.INT32.supports_ordering()
        assert EdmType.INT64.supports_ordering()
        assert EdmType.DOUBLE.supports_ordering()
        assert EdmType.DATETIME.supports_ordering()
        assert not EdmType.STRING.supports_ordering()
        assert not EdmType.BOOLEAN.supports_ordering()
        assert not EdmType.GUID.supports_ordering()


class TestTypedValue:
    """Test TypedValue container."""
    
    def test_typed_value_creation(self):
        """Test creating typed values."""
        tv = TypedValue("hello", EdmType.STRING)
        assert tv.value == "hello"
        assert tv.edm_type == EdmType.STRING
    
    def test_typed_value_immutable(self):
        """Test that typed values are immutable."""
        tv = TypedValue(42, EdmType.INT32)
        with pytest.raises(Exception):  # FrozenInstanceError
            tv.value = 100
    
    def test_typed_value_repr(self):
        """Test string representation."""
        tv = TypedValue(42, EdmType.INT32)
        assert "42" in repr(tv)
        assert "Edm.Int32" in repr(tv)


class TestTypeError:
    """Test type error exception."""
    
    def test_type_error_basic(self):
        """Test basic type error."""
        err = EdmTypeError("Type mismatch")
        assert "Type mismatch" in str(err)
    
    def test_type_error_with_position(self):
        """Test type error with position."""
        pos = Position(line=1, column=10, offset=10)
        err = EdmTypeError("Type mismatch", position=pos)
        assert "line 1" in str(err)
        assert "column 10" in str(err)
    
    def test_type_error_with_expected_actual(self):
        """Test type error with expected and actual types."""
        err = EdmTypeError(
            "Type mismatch",
            expected=EdmType.STRING,
            actual=EdmType.INT32
        )
        assert "Edm.String" in str(err)
        assert "Edm.Int32" in str(err)
        assert "Expected" in str(err)
        assert "Actual" in str(err)
    
    def test_type_error_with_multiple_expected(self):
        """Test type error with multiple expected types."""
        err = EdmTypeError(
            "Type mismatch",
            expected=[EdmType.INT32, EdmType.INT64, EdmType.DOUBLE],
            actual=EdmType.STRING
        )
        err_str = str(err)
        assert "Edm.Int32" in err_str
        assert "Edm.Int64" in err_str
        assert "Edm.Double" in err_str
    
    def test_type_error_with_suggestion(self):
        """Test type error with suggestion."""
        err = EdmTypeError(
            "Type mismatch",
            suggestion="Use numeric types"
        )
        assert "Suggestion" in str(err)
        assert "Use numeric types" in str(err)


class TestTypeInference:
    """Test type inference from Python values."""
    
    def test_infer_null(self):
        """Test null type inference."""
        validator = TypeValidator()
        assert validator.infer_type(None) == EdmType.NULL
    
    def test_infer_boolean(self):
        """Test boolean type inference."""
        validator = TypeValidator()
        assert validator.infer_type(True) == EdmType.BOOLEAN
        assert validator.infer_type(False) == EdmType.BOOLEAN
    
    def test_infer_int32(self):
        """Test Int32 type inference."""
        validator = TypeValidator()
        assert validator.infer_type(0) == EdmType.INT32
        assert validator.infer_type(42) == EdmType.INT32
        assert validator.infer_type(-100) == EdmType.INT32
        assert validator.infer_type(2147483647) == EdmType.INT32
        assert validator.infer_type(-2147483648) == EdmType.INT32
    
    def test_infer_int64(self):
        """Test Int64 type inference for large integers."""
        validator = TypeValidator()
        assert validator.infer_type(2147483648) == EdmType.INT64
        assert validator.infer_type(-2147483649) == EdmType.INT64
        assert validator.infer_type(9999999999) == EdmType.INT64
    
    def test_infer_double(self):
        """Test Double type inference."""
        validator = TypeValidator()
        assert validator.infer_type(3.14) == EdmType.DOUBLE
        assert validator.infer_type(0.0) == EdmType.DOUBLE
        assert validator.infer_type(-2.5) == EdmType.DOUBLE
    
    def test_infer_string(self):
        """Test String type inference."""
        validator = TypeValidator()
        assert validator.infer_type("") == EdmType.STRING
        assert validator.infer_type("hello") == EdmType.STRING
        assert validator.infer_type("123") == EdmType.STRING
    
    def test_infer_datetime(self):
        """Test DateTime type inference."""
        validator = TypeValidator()
        dt = datetime(2025, 12, 5, 10, 30, 0)
        assert validator.infer_type(dt) == EdmType.DATETIME
    
    def test_infer_guid(self):
        """Test Guid type inference."""
        validator = TypeValidator()
        guid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        assert validator.infer_type(guid) == EdmType.GUID
    
    def test_infer_binary(self):
        """Test Binary type inference."""
        validator = TypeValidator()
        assert validator.infer_type(b'hello') == EdmType.BINARY
        assert validator.infer_type(bytes([1, 2, 3])) == EdmType.BINARY


class TestComparisonTypeChecking:
    """Test comparison operator type checking."""
    
    def test_comparison_same_types_valid(self):
        """Test comparisons between same types."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.STRING, 'eq', EdmType.STRING)
        assert validator.check_comparison(EdmType.INT32, 'gt', EdmType.INT32)
        assert validator.check_comparison(EdmType.BOOLEAN, 'ne', EdmType.BOOLEAN)
    
    def test_comparison_numeric_promotion_valid(self):
        """Test comparisons with numeric promotion."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.INT32, 'gt', EdmType.INT64)
        assert validator.check_comparison(EdmType.INT32, 'le', EdmType.DOUBLE)
        assert validator.check_comparison(EdmType.INT64, 'ge', EdmType.DOUBLE)
    
    def test_comparison_with_null_equality(self):
        """Test null comparisons with eq/ne."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.NULL, 'eq', EdmType.STRING)
        assert validator.check_comparison(EdmType.INT32, 'ne', EdmType.NULL)
        assert validator.check_comparison(EdmType.NULL, 'eq', EdmType.NULL)
    
    def test_comparison_with_null_ordering_invalid(self):
        """Test null comparisons with ordering operators."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.NULL, 'gt', EdmType.INT32)
        assert "null" in str(exc.value).lower()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.STRING, 'lt', EdmType.NULL)
        assert "null" in str(exc.value).lower()
    
    def test_comparison_incompatible_types(self):
        """Test comparisons between incompatible types."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.STRING, 'eq', EdmType.INT32)
        assert "Cannot compare" in str(exc.value)
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.BOOLEAN, 'ne', EdmType.STRING)
        assert "Cannot compare" in str(exc.value)
    
    def test_ordering_non_orderable_types(self):
        """Test ordering operators with non-orderable types."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.STRING, 'gt', EdmType.STRING)
        # Check error message mentions the issue
        assert "gt" in str(exc.value).lower() or "ordering" in str(exc.value).lower()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.BOOLEAN, 'lt', EdmType.BOOLEAN)
        assert "lt" in str(exc.value).lower() or "ordering" in str(exc.value).lower()
    
    def test_ordering_orderable_types(self):
        """Test ordering operators with orderable types."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.INT32, 'gt', EdmType.INT32)
        assert validator.check_comparison(EdmType.INT64, 'le', EdmType.INT64)
        assert validator.check_comparison(EdmType.DOUBLE, 'ge', EdmType.DOUBLE)
        assert validator.check_comparison(EdmType.DATETIME, 'lt', EdmType.DATETIME)


class TestLogicalTypeChecking:
    """Test logical operator type checking."""
    
    def test_logical_boolean_valid(self):
        """Test logical operators with boolean operands."""
        validator = TypeValidator()
        assert validator.check_logical(EdmType.BOOLEAN, 'and')
        assert validator.check_logical(EdmType.BOOLEAN, 'or')
        assert validator.check_logical(EdmType.BOOLEAN, 'not')
    
    def test_logical_null_valid(self):
        """Test logical operators with null."""
        validator = TypeValidator()
        assert validator.check_logical(EdmType.NULL, 'and')
        assert validator.check_logical(EdmType.NULL, 'or')
        assert validator.check_logical(EdmType.NULL, 'not')
    
    def test_logical_non_boolean_invalid(self):
        """Test logical operators with non-boolean operands."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_logical(EdmType.STRING, 'and')
        assert "boolean" in str(exc.value).lower()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_logical(EdmType.INT32, 'or')
        assert "boolean" in str(exc.value).lower()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_logical(EdmType.DOUBLE, 'not')
        assert "boolean" in str(exc.value).lower()


class TestArithmeticTypeChecking:
    """Test arithmetic operator type checking."""
    
    def test_arithmetic_int32_int32(self):
        """Test Int32 + Int32 → Int32."""
        validator = TypeValidator()
        result = validator.check_arithmetic(EdmType.INT32, 'add', EdmType.INT32)
        assert result == EdmType.INT32
    
    def test_arithmetic_int32_int64(self):
        """Test Int32 + Int64 → Int64."""
        validator = TypeValidator()
        result = validator.check_arithmetic(EdmType.INT32, 'sub', EdmType.INT64)
        assert result == EdmType.INT64
    
    def test_arithmetic_int32_double(self):
        """Test Int32 + Double → Double."""
        validator = TypeValidator()
        result = validator.check_arithmetic(EdmType.INT32, 'mul', EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
    
    def test_arithmetic_int64_double(self):
        """Test Int64 + Double → Double."""
        validator = TypeValidator()
        result = validator.check_arithmetic(EdmType.INT64, 'div', EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
    
    def test_arithmetic_double_double(self):
        """Test Double + Double → Double."""
        validator = TypeValidator()
        result = validator.check_arithmetic(EdmType.DOUBLE, 'mod', EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
    
    def test_arithmetic_non_numeric_left(self):
        """Test arithmetic with non-numeric left operand."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_arithmetic(EdmType.STRING, 'add', EdmType.INT32)
        assert "arithmetic" in str(exc.value).lower()
        assert "numeric" in str(exc.value).lower()
    
    def test_arithmetic_non_numeric_right(self):
        """Test arithmetic with non-numeric right operand."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_arithmetic(EdmType.INT32, 'sub', EdmType.BOOLEAN)
        assert "arithmetic" in str(exc.value).lower()
        assert "numeric" in str(exc.value).lower()
    
    def test_arithmetic_all_operators(self):
        """Test all arithmetic operators."""
        validator = TypeValidator()
        for op in ['add', 'sub', 'mul', 'div', 'mod']:
            result = validator.check_arithmetic(EdmType.INT32, op, EdmType.INT64)
            assert result == EdmType.INT64


class TestFunctionTypeChecking:
    """Test function signature validation."""
    
    def test_string_functions(self):
        """Test string function signatures."""
        validator = TypeValidator()
        
        # startswith(string, string) -> bool
        result = validator.check_function('startswith', [EdmType.STRING, EdmType.STRING])
        assert result == EdmType.BOOLEAN
        
        # endswith(string, string) -> bool
        result = validator.check_function('endswith', [EdmType.STRING, EdmType.STRING])
        assert result == EdmType.BOOLEAN
        
        # contains(string, string) -> bool
        result = validator.check_function('contains', [EdmType.STRING, EdmType.STRING])
        assert result == EdmType.BOOLEAN
        
        # tolower(string) -> string
        result = validator.check_function('tolower', [EdmType.STRING])
        assert result == EdmType.STRING
        
        # length(string) -> int32
        result = validator.check_function('length', [EdmType.STRING])
        assert result == EdmType.INT32
    
    def test_date_functions(self):
        """Test date function signatures."""
        validator = TypeValidator()
        
        # year(datetime) -> int32
        result = validator.check_function('year', [EdmType.DATETIME])
        assert result == EdmType.INT32
        
        # month(datetime) -> int32
        result = validator.check_function('month', [EdmType.DATETIME])
        assert result == EdmType.INT32
        
        # day(datetime) -> int32
        result = validator.check_function('day', [EdmType.DATETIME])
        assert result == EdmType.INT32
    
    def test_math_functions(self):
        """Test math function signatures."""
        validator = TypeValidator()
        
        # round(double) -> double
        result = validator.check_function('round', [EdmType.DOUBLE])
        assert result == EdmType.DOUBLE
        
        # floor(double) -> double
        result = validator.check_function('floor', [EdmType.DOUBLE])
        assert result == EdmType.DOUBLE
        
        # ceiling(double) -> double
        result = validator.check_function('ceiling', [EdmType.DOUBLE])
        assert result == EdmType.DOUBLE
    
    def test_substring_two_args(self):
        """Test substring with 2 arguments."""
        validator = TypeValidator()
        result = validator.check_function('substring', [EdmType.STRING, EdmType.INT32])
        assert result == EdmType.STRING
    
    def test_substring_three_args(self):
        """Test substring with 3 arguments."""
        validator = TypeValidator()
        result = validator.check_function('substring', [EdmType.STRING, EdmType.INT32, EdmType.INT32])
        assert result == EdmType.STRING
    
    def test_substring_wrong_arg_count(self):
        """Test substring with wrong argument count."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_function('substring', [EdmType.STRING])
        assert "2 or 3 arguments" in str(exc.value)
    
    def test_function_wrong_arg_count(self):
        """Test function with wrong argument count."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_function('length', [EdmType.STRING, EdmType.STRING])
        assert "expects 1 argument" in str(exc.value)
    
    def test_function_wrong_arg_type(self):
        """Test function with wrong argument type."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_function('startswith', [EdmType.INT32, EdmType.STRING])
        assert "argument 1" in str(exc.value)
        assert "Edm.String" in str(exc.value)
        assert "Edm.Int32" in str(exc.value)
    
    def test_function_null_arguments(self):
        """Test functions with null arguments."""
        validator = TypeValidator()
        # Null is allowed for any argument
        result = validator.check_function('startswith', [EdmType.NULL, EdmType.STRING])
        assert result == EdmType.BOOLEAN
        
        result = validator.check_function('length', [EdmType.NULL])
        assert result == EdmType.INT32
    
    def test_function_numeric_promotion(self):
        """Test functions with numeric argument promotion."""
        validator = TypeValidator()
        # substring accepts any numeric type for start/length
        result = validator.check_function('substring', [EdmType.STRING, EdmType.INT64])
        assert result == EdmType.STRING
    
    def test_unknown_function(self):
        """Test unknown function."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError) as exc:
            validator.check_function('unknown_func', [EdmType.STRING])
        assert "Unknown function" in str(exc.value)


class TestNumericPromotion:
    """Test numeric type promotion."""
    
    def test_promote_int32_int32(self):
        """Test Int32 + Int32 → Int32."""
        validator = TypeValidator()
        result = validator.promote(EdmType.INT32, EdmType.INT32)
        assert result == EdmType.INT32
    
    def test_promote_int32_int64(self):
        """Test Int32 + Int64 → Int64."""
        validator = TypeValidator()
        result = validator.promote(EdmType.INT32, EdmType.INT64)
        assert result == EdmType.INT64
        result = validator.promote(EdmType.INT64, EdmType.INT32)
        assert result == EdmType.INT64
    
    def test_promote_int32_double(self):
        """Test Int32 + Double → Double."""
        validator = TypeValidator()
        result = validator.promote(EdmType.INT32, EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
        result = validator.promote(EdmType.DOUBLE, EdmType.INT32)
        assert result == EdmType.DOUBLE
    
    def test_promote_int64_int64(self):
        """Test Int64 + Int64 → Int64."""
        validator = TypeValidator()
        result = validator.promote(EdmType.INT64, EdmType.INT64)
        assert result == EdmType.INT64
    
    def test_promote_int64_double(self):
        """Test Int64 + Double → Double."""
        validator = TypeValidator()
        result = validator.promote(EdmType.INT64, EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
        result = validator.promote(EdmType.DOUBLE, EdmType.INT64)
        assert result == EdmType.DOUBLE
    
    def test_promote_double_double(self):
        """Test Double + Double → Double."""
        validator = TypeValidator()
        result = validator.promote(EdmType.DOUBLE, EdmType.DOUBLE)
        assert result == EdmType.DOUBLE
    
    def test_promote_non_numeric(self):
        """Test promotion of non-numeric types fails."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError):
            validator.promote(EdmType.STRING, EdmType.INT32)
        with pytest.raises(EdmTypeError):
            validator.promote(EdmType.BOOLEAN, EdmType.DOUBLE)


class TestTypeConversion:
    """Test type conversion."""
    
    def test_convert_same_type(self):
        """Test conversion to same type."""
        validator = TypeValidator()
        assert validator.convert(42, EdmType.INT32, EdmType.INT32) == 42
        assert validator.convert("hello", EdmType.STRING, EdmType.STRING) == "hello"
    
    def test_convert_int32_to_int64(self):
        """Test Int32 → Int64."""
        validator = TypeValidator()
        result = validator.convert(42, EdmType.INT32, EdmType.INT64)
        assert result == 42
        assert isinstance(result, int)
    
    def test_convert_int32_to_double(self):
        """Test Int32 → Double."""
        validator = TypeValidator()
        result = validator.convert(42, EdmType.INT32, EdmType.DOUBLE)
        assert result == 42.0
        assert isinstance(result, float)
    
    def test_convert_int64_to_double(self):
        """Test Int64 → Double."""
        validator = TypeValidator()
        result = validator.convert(9999999999, EdmType.INT64, EdmType.DOUBLE)
        assert isinstance(result, float)
    
    def test_convert_double_to_int32(self):
        """Test Double → Int32."""
        validator = TypeValidator()
        result = validator.convert(42.7, EdmType.DOUBLE, EdmType.INT32)
        assert result == 42
        assert isinstance(result, int)
    
    def test_convert_null(self):
        """Test null conversions."""
        validator = TypeValidator()
        assert validator.convert(None, EdmType.NULL, EdmType.STRING) is None
        assert validator.convert("hello", EdmType.STRING, EdmType.NULL) is None
    
    def test_convert_to_string(self):
        """Test explicit conversion to string."""
        validator = TypeValidator()
        assert validator.convert(42, EdmType.INT32, EdmType.STRING) == "42"
        assert validator.convert(True, EdmType.BOOLEAN, EdmType.STRING) == "True"
    
    def test_convert_invalid(self):
        """Test invalid conversions."""
        validator = TypeValidator()
        with pytest.raises(EdmTypeError):
            validator.convert("hello", EdmType.STRING, EdmType.INT32)


class TestNullHandling:
    """Test null handling throughout type system."""
    
    def test_null_comparison_with_eq(self):
        """Test null comparisons with eq."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.NULL, 'eq', EdmType.NULL)
        assert validator.check_comparison(EdmType.NULL, 'eq', EdmType.STRING)
        assert validator.check_comparison(EdmType.INT32, 'eq', EdmType.NULL)
    
    def test_null_comparison_with_ne(self):
        """Test null comparisons with ne."""
        validator = TypeValidator()
        assert validator.check_comparison(EdmType.NULL, 'ne', EdmType.NULL)
        assert validator.check_comparison(EdmType.NULL, 'ne', EdmType.BOOLEAN)
        assert validator.check_comparison(EdmType.DOUBLE, 'ne', EdmType.NULL)
    
    def test_null_with_ordering_operators(self):
        """Test null with ordering operators (should fail)."""
        validator = TypeValidator()
        for op in ['gt', 'ge', 'lt', 'le']:
            with pytest.raises(EdmTypeError):
                validator.check_comparison(EdmType.NULL, op, EdmType.INT32)
            with pytest.raises(EdmTypeError):
                validator.check_comparison(EdmType.STRING, op, EdmType.NULL)
    
    def test_null_in_logical_operations(self):
        """Test null in logical operations."""
        validator = TypeValidator()
        assert validator.check_logical(EdmType.NULL, 'and')
        assert validator.check_logical(EdmType.NULL, 'or')
        assert validator.check_logical(EdmType.NULL, 'not')
    
    def test_null_in_function_arguments(self):
        """Test null as function argument."""
        validator = TypeValidator()
        result = validator.check_function('length', [EdmType.NULL])
        assert result == EdmType.INT32
        
        result = validator.check_function('startswith', [EdmType.NULL, EdmType.STRING])
        assert result == EdmType.BOOLEAN


class TestErrorMessages:
    """Test error message quality."""
    
    def test_error_includes_position(self):
        """Test error messages include position."""
        validator = TypeValidator()
        pos = Position(line=5, column=20, offset=100)
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(
                EdmType.STRING,
                'eq',
                EdmType.INT32,
                position=pos
            )
        
        err_msg = str(exc.value)
        assert "line 5" in err_msg
        assert "column 20" in err_msg
    
    def test_error_shows_expected_vs_actual(self):
        """Test error messages show expected vs actual types."""
        validator = TypeValidator()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_function('length', [EdmType.INT32])
        
        err_msg = str(exc.value)
        assert "Edm.String" in err_msg  # Expected
        assert "Edm.Int32" in err_msg   # Actual
        assert "Expected" in err_msg
        assert "Actual" in err_msg
    
    def test_error_includes_suggestion(self):
        """Test error messages include helpful suggestions."""
        validator = TypeValidator()
        
        with pytest.raises(EdmTypeError) as exc:
            validator.check_comparison(EdmType.NULL, 'gt', EdmType.INT32)
        
        err_msg = str(exc.value)
        assert "Suggestion" in err_msg or "eq" in err_msg.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_int32_boundary_values(self):
        """Test Int32 boundary value inference."""
        validator = TypeValidator()
        
        # At boundaries
        assert validator.infer_type(2147483647) == EdmType.INT32
        assert validator.infer_type(-2147483648) == EdmType.INT32
        
        # Just outside boundaries
        assert validator.infer_type(2147483648) == EdmType.INT64
        assert validator.infer_type(-2147483649) == EdmType.INT64
    
    def test_empty_string(self):
        """Test empty string handling."""
        validator = TypeValidator()
        assert validator.infer_type("") == EdmType.STRING
    
    def test_zero_values(self):
        """Test zero value handling."""
        validator = TypeValidator()
        assert validator.infer_type(0) == EdmType.INT32
        assert validator.infer_type(0.0) == EdmType.DOUBLE
    
    def test_boolean_vs_int(self):
        """Test that boolean is detected before int."""
        validator = TypeValidator()
        # In Python, bool is subclass of int
        # But we must detect bool first
        assert validator.infer_type(True) == EdmType.BOOLEAN
        assert validator.infer_type(False) == EdmType.BOOLEAN
        assert validator.infer_type(1) == EdmType.INT32
        assert validator.infer_type(0) == EdmType.INT32
