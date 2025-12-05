"""
OData EDM (Entity Data Model) Type System for Azure Table Storage.

This module implements the complete type system for OData v3 queries,
including type inference, validation, compatibility checking, and conversions.

References:
    - OData v3 Primitive Data Types
    - Azure Table Storage Entity Properties
    - EDM Type System Specification
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union
from datetime import datetime
import uuid

from .lexer import Position


class EdmType(Enum):
    """
    Entity Data Model primitive types.
    
    Represents the complete set of types supported by Azure Table Storage
    and OData v3 filter expressions.
    """
    STRING = "Edm.String"
    INT32 = "Edm.Int32"
    INT64 = "Edm.Int64"
    DOUBLE = "Edm.Double"
    BOOLEAN = "Edm.Boolean"
    DATETIME = "Edm.DateTime"
    GUID = "Edm.Guid"
    BINARY = "Edm.Binary"
    NULL = "Edm.Null"
    
    def is_numeric(self) -> bool:
        """Check if type is numeric (Int32, Int64, Double)."""
        return self in (EdmType.INT32, EdmType.INT64, EdmType.DOUBLE)
    
    def is_comparable(self, other: EdmType) -> bool:
        """
        Check if two types can be compared.
        
        Comparison rules:
        - Numeric types can compare with each other (with promotion)
        - Same types can compare
        - Null can compare with any type
        
        Args:
            other: Type to compare with
            
        Returns:
            True if types are comparable
        """
        # Null can compare with anything
        if self == EdmType.NULL or other == EdmType.NULL:
            return True
        
        # Numeric types can compare with each other
        if self.is_numeric() and other.is_numeric():
            return True
        
        # Same types can compare
        if self == other:
            return True
        
        return False
    
    def supports_ordering(self) -> bool:
        """Check if type supports ordering (gt, ge, lt, le)."""
        return self in (
            EdmType.INT32,
            EdmType.INT64,
            EdmType.DOUBLE,
            EdmType.DATETIME,
        )


@dataclass(frozen=True)
class TypedValue:
    """
    Value with its EDM type.
    
    Immutable container for a value and its associated type information.
    Used throughout the type system for type-safe value handling.
    """
    value: Any
    edm_type: EdmType
    
    def __repr__(self) -> str:
        return f"TypedValue({self.value!r}, {self.edm_type.value})"


class TypeError(Exception):
    """
    Type validation error.
    
    Raised when type checking fails, with detailed information about
    the expected vs actual types and position in source.
    """
    
    def __init__(
        self,
        message: str,
        position: Optional[Position] = None,
        expected: Optional[Union[EdmType, list[EdmType]]] = None,
        actual: Optional[EdmType] = None,
        suggestion: Optional[str] = None
    ):
        """
        Initialize type error.
        
        Args:
            message: Error message
            position: Position in source where error occurred
            expected: Expected type(s)
            actual: Actual type encountered
            suggestion: Suggestion for fixing the error
        """
        super().__init__(message)
        self.position = position
        self.expected = expected
        self.actual = actual
        self.suggestion = suggestion
    
    def __str__(self) -> str:
        """Format error message with position and suggestions."""
        lines = []
        
        if self.position:
            lines.append(
                f"Type Error at line {self.position.line}, "
                f"column {self.position.column}:"
            )
        else:
            lines.append("Type Error:")
        
        lines.append(f"  {self.args[0]}")
        
        if self.expected and self.actual:
            if isinstance(self.expected, list):
                expected_str = ", ".join(t.value for t in self.expected)
                lines.append(f"  Expected: {expected_str}")
            else:
                lines.append(f"  Expected: {self.expected.value}")
            lines.append(f"  Actual: {self.actual.value}")
        
        if self.suggestion:
            lines.append(f"  Suggestion: {self.suggestion}")
        
        return "\n".join(lines)


class TypeValidator:
    """
    Validates type compatibility and performs conversions.
    
    Implements the complete type checking logic for OData expressions,
    including comparison operators, logical operators, arithmetic operators,
    and function calls.
    """
    
    # Function signatures: function_name -> (arg_types, return_type)
    FUNCTION_SIGNATURES = {
        # String functions
        'startswith': ([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN),
        'endswith': ([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN),
        'contains': ([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN),
        'substringof': ([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN),
        'tolower': ([EdmType.STRING], EdmType.STRING),
        'toupper': ([EdmType.STRING], EdmType.STRING),
        'trim': ([EdmType.STRING], EdmType.STRING),
        'concat': ([EdmType.STRING, EdmType.STRING], EdmType.STRING),
        'length': ([EdmType.STRING], EdmType.INT32),
        'indexof': ([EdmType.STRING, EdmType.STRING], EdmType.INT32),
        'replace': ([EdmType.STRING, EdmType.STRING, EdmType.STRING], EdmType.STRING),
        # substring has two overloads
        'substring': None,  # Special case: handled separately
        # Date functions
        'year': ([EdmType.DATETIME], EdmType.INT32),
        'month': ([EdmType.DATETIME], EdmType.INT32),
        'day': ([EdmType.DATETIME], EdmType.INT32),
        'hour': ([EdmType.DATETIME], EdmType.INT32),
        'minute': ([EdmType.DATETIME], EdmType.INT32),
        'second': ([EdmType.DATETIME], EdmType.INT32),
        # Math functions
        'round': ([EdmType.DOUBLE], EdmType.DOUBLE),
        'floor': ([EdmType.DOUBLE], EdmType.DOUBLE),
        'ceiling': ([EdmType.DOUBLE], EdmType.DOUBLE),
    }
    
    def check_comparison(
        self,
        left: EdmType,
        operator: str,
        right: EdmType,
        position: Optional[Position] = None
    ) -> bool:
        """
        Check if comparison is valid.
        
        Args:
            left: Left operand type
            operator: Comparison operator (eq, ne, gt, ge, lt, le)
            right: Right operand type
            position: Position in source for error reporting
            
        Returns:
            True if comparison is valid
            
        Raises:
            TypeError: If types are incompatible
        """
        # Check basic comparability
        if not left.is_comparable(right):
            raise TypeError(
                f"Cannot compare {left.value} with {right.value}",
                position=position,
                expected=left,
                actual=right,
                suggestion="Ensure both operands have compatible types"
            )
        
        # For ordering operators (gt, ge, lt, le), check if types support ordering
        if operator in ('gt', 'ge', 'lt', 'le'):
            # Null comparisons only support eq/ne
            if left == EdmType.NULL or right == EdmType.NULL:
                raise TypeError(
                    f"Cannot use '{operator}' with null values",
                    position=position,
                    suggestion="Use 'eq' or 'ne' for null comparisons"
                )
            
            # Promote to common type
            if left.is_numeric() and right.is_numeric():
                common_type = self.promote(left, right)
                if not common_type.supports_ordering():
                    raise TypeError(
                        f"Type {common_type.value} does not support ordering operators",
                        position=position
                    )
            else:
                # For non-numeric types, both must support ordering
                if not left.supports_ordering() or not right.supports_ordering():
                    non_ordering = left if not left.supports_ordering() else right
                    raise TypeError(
                        f"Cannot use '{operator}' with {non_ordering.value}",
                        position=position,
                        expected=[EdmType.INT32, EdmType.INT64, EdmType.DOUBLE, EdmType.DATETIME],
                        actual=non_ordering,
                        suggestion="Use 'eq' or 'ne' for equality comparisons only"
                    )
        
        return True
    
    def check_logical(
        self,
        operand_type: EdmType,
        operator: str,
        position: Optional[Position] = None
    ) -> bool:
        """
        Check if logical operation is valid.
        
        Args:
            operand_type: Operand type
            operator: Logical operator (and, or, not)
            position: Position in source for error reporting
            
        Returns:
            True if operation is valid
            
        Raises:
            TypeError: If type is not boolean
        """
        # Logical operators require boolean operands
        if operand_type != EdmType.BOOLEAN and operand_type != EdmType.NULL:
            raise TypeError(
                f"Logical operator '{operator}' requires boolean operands",
                position=position,
                expected=EdmType.BOOLEAN,
                actual=operand_type,
                suggestion="Ensure the expression evaluates to a boolean value"
            )
        
        return True
    
    def check_arithmetic(
        self,
        left: EdmType,
        operator: str,
        right: EdmType,
        position: Optional[Position] = None
    ) -> EdmType:
        """
        Check if arithmetic operation is valid and return result type.
        
        Args:
            left: Left operand type
            operator: Arithmetic operator (add, sub, mul, div, mod)
            right: Right operand type
            position: Position in source for error reporting
            
        Returns:
            Result type after numeric promotion
            
        Raises:
            TypeError: If types are not numeric
        """
        # Both operands must be numeric
        if not left.is_numeric():
            raise TypeError(
                f"Cannot use arithmetic operator '{operator}' with {left.value}",
                position=position,
                expected=[EdmType.INT32, EdmType.INT64, EdmType.DOUBLE],
                actual=left,
                suggestion="Arithmetic operators require numeric types"
            )
        
        if not right.is_numeric():
            raise TypeError(
                f"Cannot use arithmetic operator '{operator}' with {right.value}",
                position=position,
                expected=[EdmType.INT32, EdmType.INT64, EdmType.DOUBLE],
                actual=right,
                suggestion="Arithmetic operators require numeric types"
            )
        
        # Return promoted type
        return self.promote(left, right)
    
    def check_function(
        self,
        function: str,
        args: list[EdmType],
        position: Optional[Position] = None
    ) -> EdmType:
        """
        Check function signature and return result type.
        
        Args:
            function: Function name (lowercase)
            args: Argument types
            position: Position in source for error reporting
            
        Returns:
            Function return type
            
        Raises:
            TypeError: If function signature doesn't match
        """
        # Handle substring overloads specially
        if function == 'substring':
            if len(args) == 2:
                # substring(string, start)
                if args[0] != EdmType.STRING:
                    raise TypeError(
                        f"Function 'substring' expects first argument to be Edm.String",
                        position=position,
                        expected=EdmType.STRING,
                        actual=args[0]
                    )
                if not args[1].is_numeric():
                    raise TypeError(
                        f"Function 'substring' expects second argument to be numeric",
                        position=position,
                        expected=[EdmType.INT32, EdmType.INT64],
                        actual=args[1]
                    )
                return EdmType.STRING
            elif len(args) == 3:
                # substring(string, start, length)
                if args[0] != EdmType.STRING:
                    raise TypeError(
                        f"Function 'substring' expects first argument to be Edm.String",
                        position=position,
                        expected=EdmType.STRING,
                        actual=args[0]
                    )
                if not args[1].is_numeric() or not args[2].is_numeric():
                    raise TypeError(
                        f"Function 'substring' expects numeric arguments for start and length",
                        position=position
                    )
                return EdmType.STRING
            else:
                raise TypeError(
                    f"Function 'substring' expects 2 or 3 arguments, got {len(args)}",
                    position=position
                )
        
        # Look up function signature
        if function not in self.FUNCTION_SIGNATURES:
            raise TypeError(
                f"Unknown function '{function}'",
                position=position,
                suggestion="Check function name spelling"
            )
        
        signature = self.FUNCTION_SIGNATURES[function]
        expected_args, return_type = signature
        
        # Check argument count
        if len(args) != len(expected_args):
            raise TypeError(
                f"Function '{function}' expects {len(expected_args)} argument(s), "
                f"got {len(args)}",
                position=position
            )
        
        # Check argument types
        for i, (expected, actual) in enumerate(zip(expected_args, args)):
            # Allow null for any argument
            if actual == EdmType.NULL:
                continue
            
            # For numeric expected types, allow numeric promotion
            if expected.is_numeric() and actual.is_numeric():
                continue
            
            # Otherwise, types must match exactly
            if expected != actual:
                raise TypeError(
                    f"Function '{function}' argument {i+1}: "
                    f"expected {expected.value}, got {actual.value}",
                    position=position,
                    expected=expected,
                    actual=actual
                )
        
        return return_type
    
    def promote(self, type1: EdmType, type2: EdmType) -> EdmType:
        """
        Perform numeric type promotion.
        
        Promotion rules:
        - Int32 + Int32 → Int32
        - Int32 + Int64 → Int64
        - Int32 + Double → Double
        - Int64 + Int64 → Int64
        - Int64 + Double → Double
        - Double + Double → Double
        
        Args:
            type1: First type
            type2: Second type
            
        Returns:
            Promoted type
            
        Raises:
            TypeError: If types cannot be promoted
        """
        if not type1.is_numeric() or not type2.is_numeric():
            raise TypeError(
                f"Cannot promote non-numeric types: {type1.value}, {type2.value}"
            )
        
        # Define promotion hierarchy: Int32 < Int64 < Double
        hierarchy = {
            EdmType.INT32: 1,
            EdmType.INT64: 2,
            EdmType.DOUBLE: 3,
        }
        
        # Return the higher type in the hierarchy
        if hierarchy[type1] >= hierarchy[type2]:
            return type1
        else:
            return type2
    
    def convert(
        self,
        value: Any,
        from_type: EdmType,
        to_type: EdmType
    ) -> Any:
        """
        Perform explicit type conversion.
        
        Args:
            value: Value to convert
            from_type: Source type
            to_type: Target type
            
        Returns:
            Converted value
            
        Raises:
            TypeError: If conversion is not possible
            ValueError: If value cannot be converted
        """
        # No conversion needed
        if from_type == to_type:
            return value
        
        # Null conversions
        if from_type == EdmType.NULL:
            return None
        if to_type == EdmType.NULL:
            return None
        
        # Numeric conversions
        if from_type.is_numeric() and to_type.is_numeric():
            try:
                if to_type == EdmType.INT32:
                    return int(value)
                elif to_type == EdmType.INT64:
                    return int(value)
                elif to_type == EdmType.DOUBLE:
                    return float(value)
            except (ValueError, OverflowError) as e:
                raise ValueError(
                    f"Cannot convert {value} from {from_type.value} to {to_type.value}: {e}"
                )
        
        # String conversions (explicit only)
        if to_type == EdmType.STRING:
            return str(value)
        
        # No implicit conversions for other types
        raise TypeError(
            f"Cannot convert from {from_type.value} to {to_type.value}",
            suggestion="Explicit type conversion required"
        )
    
    def infer_type(self, value: Any) -> EdmType:
        """
        Infer EDM type from Python value.
        
        Args:
            value: Python value
            
        Returns:
            Inferred EDM type
        """
        if value is None:
            return EdmType.NULL
        elif isinstance(value, bool):
            # Must check bool before int (bool is subclass of int)
            return EdmType.BOOLEAN
        elif isinstance(value, int):
            # Use Int32 for small integers, Int64 for large
            if -2147483648 <= value <= 2147483647:
                return EdmType.INT32
            else:
                return EdmType.INT64
        elif isinstance(value, float):
            return EdmType.DOUBLE
        elif isinstance(value, str):
            return EdmType.STRING
        elif isinstance(value, datetime):
            return EdmType.DATETIME
        elif isinstance(value, uuid.UUID):
            return EdmType.GUID
        elif isinstance(value, bytes):
            return EdmType.BINARY
        else:
            # Default to string for unknown types
            return EdmType.STRING
