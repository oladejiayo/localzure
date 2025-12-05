"""
OData Function Library for Azure Table Storage.

Implements the complete set of OData v3 functions supported by Azure Table Storage,
including string, date, math, and type functions.

All string comparisons follow Azure Table Storage semantics:
- Case-insensitive for comparison functions (startswith, endswith, contains)
- Returns null when any argument is null (null propagation)
- Unicode (UTF-8) support

References:
    - OData v3 String Functions
    - OData v3 Date and Time Functions
    - OData v3 Math Functions
    - Azure Table Storage Query Functions
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional, Callable, Union
from dataclasses import dataclass

from .types import EdmType, TypedValue, TypeError as EdmTypeError


@dataclass(frozen=True)
class FunctionSignature:
    """
    Function signature definition.
    
    Defines the expected argument types and return type for a function.
    """
    arg_types: list[EdmType]
    return_type: EdmType
    allow_numeric_promotion: bool = False
    
    def __repr__(self) -> str:
        args = ", ".join(t.value for t in self.arg_types)
        return f"({args}) -> {self.return_type.value}"


class FunctionLibrary:
    """
    OData function implementations.
    
    All functions follow Azure Table Storage semantics:
    - Null arguments propagate to null results
    - String functions are case-insensitive where applicable
    - Date functions work with datetime objects
    - Math functions work with numeric types
    """
    
    # ==================== String Functions ====================
    
    @staticmethod
    def startswith(s: Optional[str], prefix: Optional[str]) -> Optional[bool]:
        """
        Check if string starts with prefix (case-insensitive).
        
        Args:
            s: String to check
            prefix: Prefix to look for
            
        Returns:
            True if s starts with prefix, False otherwise, None if either is None
            
        Example:
            >>> FunctionLibrary.startswith("HelloWorld", "hello")
            True
        """
        if s is None or prefix is None:
            return None
        return s.lower().startswith(prefix.lower())
    
    @staticmethod
    def endswith(s: Optional[str], suffix: Optional[str]) -> Optional[bool]:
        """
        Check if string ends with suffix (case-insensitive).
        
        Args:
            s: String to check
            suffix: Suffix to look for
            
        Returns:
            True if s ends with suffix, False otherwise, None if either is None
            
        Example:
            >>> FunctionLibrary.endswith("HelloWorld", "WORLD")
            True
        """
        if s is None or suffix is None:
            return None
        return s.lower().endswith(suffix.lower())
    
    @staticmethod
    def contains(s: Optional[str], substring: Optional[str]) -> Optional[bool]:
        """
        Check if string contains substring (case-insensitive).
        
        Note: This is Azure-specific. OData v3 uses substringof with reversed arguments.
        
        Args:
            s: String to check
            substring: Substring to look for
            
        Returns:
            True if s contains substring, False otherwise, None if either is None
            
        Example:
            >>> FunctionLibrary.contains("HelloWorld", "LOW")
            True
        """
        if s is None or substring is None:
            return None
        return substring.lower() in s.lower()
    
    @staticmethod
    def substringof(substring: Optional[str], s: Optional[str]) -> Optional[bool]:
        """
        Check if substring is found in string (case-insensitive).
        
        Note: OData v3 function with reversed argument order compared to contains.
        substringof('lo', 'HelloWorld') checks if 'lo' is in 'HelloWorld'.
        
        Args:
            substring: Substring to look for
            s: String to check
            
        Returns:
            True if substring is in s, False otherwise, None if either is None
            
        Example:
            >>> FunctionLibrary.substringof("LOW", "HelloWorld")
            True
        """
        if substring is None or s is None:
            return None
        return substring.lower() in s.lower()
    
    @staticmethod
    def tolower(s: Optional[str]) -> Optional[str]:
        """
        Convert string to lowercase.
        
        Args:
            s: String to convert
            
        Returns:
            Lowercase string, None if input is None
            
        Example:
            >>> FunctionLibrary.tolower("HelloWorld")
            'helloworld'
        """
        if s is None:
            return None
        return s.lower()
    
    @staticmethod
    def toupper(s: Optional[str]) -> Optional[str]:
        """
        Convert string to uppercase.
        
        Args:
            s: String to convert
            
        Returns:
            Uppercase string, None if input is None
            
        Example:
            >>> FunctionLibrary.toupper("HelloWorld")
            'HELLOWORLD'
        """
        if s is None:
            return None
        return s.upper()
    
    @staticmethod
    def trim(s: Optional[str]) -> Optional[str]:
        """
        Remove leading and trailing whitespace.
        
        Args:
            s: String to trim
            
        Returns:
            Trimmed string, None if input is None
            
        Example:
            >>> FunctionLibrary.trim("  hello  ")
            'hello'
        """
        if s is None:
            return None
        return s.strip()
    
    @staticmethod
    def concat(s1: Optional[str], s2: Optional[str]) -> Optional[str]:
        """
        Concatenate two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Concatenated string, None if either input is None
            
        Example:
            >>> FunctionLibrary.concat("Hello", "World")
            'HelloWorld'
        """
        if s1 is None or s2 is None:
            return None
        return s1 + s2
    
    @staticmethod
    def substring(s: Optional[str], start: Optional[int], length: Optional[int] = None) -> Optional[str]:
        """
        Extract substring from string.
        
        Supports two forms:
        - substring(s, start): Extract from start to end
        - substring(s, start, length): Extract length characters from start
        
        Args:
            s: Source string
            start: Starting position (0-based)
            length: Number of characters to extract (optional)
            
        Returns:
            Substring, None if any input is None
            
        Example:
            >>> FunctionLibrary.substring("HelloWorld", 5)
            'World'
            >>> FunctionLibrary.substring("HelloWorld", 0, 5)
            'Hello'
        """
        if s is None or start is None:
            return None
        
        # Convert to int if needed
        start_int = int(start)
        
        # Handle negative indices
        if start_int < 0:
            start_int = 0
        
        if length is None:
            # substring(s, start) - from start to end
            return s[start_int:]
        else:
            # substring(s, start, length) - extract length chars
            length_int = int(length)
            if length_int < 0:
                length_int = 0
            return s[start_int:start_int + length_int]
    
    @staticmethod
    def length(s: Optional[str]) -> Optional[int]:
        """
        Get string length.
        
        Args:
            s: String to measure
            
        Returns:
            Length of string, None if input is None
            
        Example:
            >>> FunctionLibrary.length("HelloWorld")
            10
        """
        if s is None:
            return None
        return len(s)
    
    @staticmethod
    def indexof(s: Optional[str], substring: Optional[str]) -> Optional[int]:
        """
        Find index of substring in string (case-sensitive).
        
        Args:
            s: String to search in
            substring: Substring to find
            
        Returns:
            Index of substring (0-based), -1 if not found, None if any input is None
            
        Example:
            >>> FunctionLibrary.indexof("HelloWorld", "World")
            5
            >>> FunctionLibrary.indexof("HelloWorld", "xyz")
            -1
        """
        if s is None or substring is None:
            return None
        
        try:
            return s.index(substring)
        except ValueError:
            return -1
    
    @staticmethod
    def replace(s: Optional[str], find: Optional[str], replace_with: Optional[str]) -> Optional[str]:
        """
        Replace all occurrences of substring (case-sensitive).
        
        Args:
            s: Source string
            find: Substring to find
            replace_with: Replacement string
            
        Returns:
            String with replacements, None if any input is None
            
        Example:
            >>> FunctionLibrary.replace("HelloWorld", "World", "Azure")
            'HelloAzure'
        """
        if s is None or find is None or replace_with is None:
            return None
        return s.replace(find, replace_with)
    
    # ==================== Date Functions ====================
    
    @staticmethod
    def year(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract year from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Year (e.g., 2025), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.year(datetime(2025, 12, 5))
            2025
        """
        if dt is None:
            return None
        return dt.year
    
    @staticmethod
    def month(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract month from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Month (1-12), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.month(datetime(2025, 12, 5))
            12
        """
        if dt is None:
            return None
        return dt.month
    
    @staticmethod
    def day(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract day from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Day (1-31), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.day(datetime(2025, 12, 5))
            5
        """
        if dt is None:
            return None
        return dt.day
    
    @staticmethod
    def hour(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract hour from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Hour (0-23), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.hour(datetime(2025, 12, 5, 14, 30))
            14
        """
        if dt is None:
            return None
        return dt.hour
    
    @staticmethod
    def minute(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract minute from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Minute (0-59), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.minute(datetime(2025, 12, 5, 14, 30))
            30
        """
        if dt is None:
            return None
        return dt.minute
    
    @staticmethod
    def second(dt: Optional[datetime]) -> Optional[int]:
        """
        Extract second from datetime.
        
        Args:
            dt: Datetime value
            
        Returns:
            Second (0-59), None if input is None
            
        Example:
            >>> from datetime import datetime
            >>> FunctionLibrary.second(datetime(2025, 12, 5, 14, 30, 45))
            45
        """
        if dt is None:
            return None
        return dt.second
    
    # ==================== Math Functions ====================
    
    @staticmethod
    def round_func(value: Optional[Union[int, float]]) -> Optional[float]:
        """
        Round to nearest integer.
        
        Args:
            value: Numeric value to round
            
        Returns:
            Rounded value, None if input is None
            
        Example:
            >>> FunctionLibrary.round_func(3.7)
            4.0
            >>> FunctionLibrary.round_func(3.2)
            3.0
        """
        if value is None:
            return None
        return float(round(value))
    
    @staticmethod
    def floor(value: Optional[Union[int, float]]) -> Optional[float]:
        """
        Round down to nearest integer.
        
        Args:
            value: Numeric value
            
        Returns:
            Floor value, None if input is None
            
        Example:
            >>> FunctionLibrary.floor(3.7)
            3.0
            >>> FunctionLibrary.floor(-3.2)
            -4.0
        """
        if value is None:
            return None
        return float(math.floor(value))
    
    @staticmethod
    def ceiling(value: Optional[Union[int, float]]) -> Optional[float]:
        """
        Round up to nearest integer.
        
        Args:
            value: Numeric value
            
        Returns:
            Ceiling value, None if input is None
            
        Example:
            >>> FunctionLibrary.ceiling(3.2)
            4.0
            >>> FunctionLibrary.ceiling(-3.7)
            -3.0
        """
        if value is None:
            return None
        return float(math.ceil(value))
    
    # ==================== Type Functions ====================
    
    @staticmethod
    def isof(value: Any, type_name: str) -> bool:
        """
        Check if value is of specified type.
        
        Args:
            value: Value to check
            type_name: EDM type name (e.g., "Edm.String")
            
        Returns:
            True if value is of specified type
            
        Example:
            >>> FunctionLibrary.isof("hello", "Edm.String")
            True
            >>> FunctionLibrary.isof(42, "Edm.String")
            False
        """
        # Map type names to Python types
        type_map = {
            "Edm.String": str,
            "Edm.Int32": int,
            "Edm.Int64": int,
            "Edm.Double": (int, float),
            "Edm.Boolean": bool,
            "Edm.DateTime": datetime,
            "Edm.Null": type(None),
        }
        
        if value is None:
            return type_name == "Edm.Null"
        
        expected_type = type_map.get(type_name)
        if expected_type is None:
            return False
        
        # Special case for boolean (must check before int)
        if type_name == "Edm.Boolean":
            return isinstance(value, bool)
        
        return isinstance(value, expected_type)
    
    @staticmethod
    def cast(value: Any, type_name: str) -> Any:
        """
        Cast value to specified type.
        
        Args:
            value: Value to cast
            type_name: EDM type name (e.g., "Edm.String")
            
        Returns:
            Casted value
            
        Raises:
            ValueError: If cast is not possible
            
        Example:
            >>> FunctionLibrary.cast(42, "Edm.String")
            '42'
            >>> FunctionLibrary.cast("42", "Edm.Int32")
            42
        """
        if value is None:
            return None
        
        try:
            if type_name == "Edm.String":
                return str(value)
            elif type_name == "Edm.Int32":
                return int(value)
            elif type_name == "Edm.Int64":
                return int(value)
            elif type_name == "Edm.Double":
                return float(value)
            elif type_name == "Edm.Boolean":
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes')
                return bool(value)
            else:
                raise ValueError(f"Cannot cast to {type_name}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot cast {value!r} to {type_name}: {e}")


class FunctionRegistry:
    """
    Registry of all available OData functions.
    
    Provides function lookup, signature validation, and execution.
    """
    
    def __init__(self):
        """Initialize function registry with all OData functions."""
        self._functions: dict[str, tuple[Callable, FunctionSignature]] = {}
        self._register_all()
    
    def _register_all(self):
        """Register all OData functions with their signatures."""
        lib = FunctionLibrary
        
        # String functions
        self.register('startswith', lib.startswith, 
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN))
        self.register('endswith', lib.endswith,
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN))
        self.register('contains', lib.contains,
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN))
        self.register('substringof', lib.substringof,
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.BOOLEAN))
        self.register('tolower', lib.tolower,
                     FunctionSignature([EdmType.STRING], EdmType.STRING))
        self.register('toupper', lib.toupper,
                     FunctionSignature([EdmType.STRING], EdmType.STRING))
        self.register('trim', lib.trim,
                     FunctionSignature([EdmType.STRING], EdmType.STRING))
        self.register('concat', lib.concat,
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.STRING))
        self.register('length', lib.length,
                     FunctionSignature([EdmType.STRING], EdmType.INT32))
        self.register('indexof', lib.indexof,
                     FunctionSignature([EdmType.STRING, EdmType.STRING], EdmType.INT32))
        self.register('replace', lib.replace,
                     FunctionSignature([EdmType.STRING, EdmType.STRING, EdmType.STRING], EdmType.STRING))
        
        # Note: substring has variable arguments, handled specially in call()
        
        # Date functions
        self.register('year', lib.year,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        self.register('month', lib.month,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        self.register('day', lib.day,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        self.register('hour', lib.hour,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        self.register('minute', lib.minute,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        self.register('second', lib.second,
                     FunctionSignature([EdmType.DATETIME], EdmType.INT32))
        
        # Math functions (allow numeric promotion)
        self.register('round', lib.round_func,
                     FunctionSignature([EdmType.DOUBLE], EdmType.DOUBLE, allow_numeric_promotion=True))
        self.register('floor', lib.floor,
                     FunctionSignature([EdmType.DOUBLE], EdmType.DOUBLE, allow_numeric_promotion=True))
        self.register('ceiling', lib.ceiling,
                     FunctionSignature([EdmType.DOUBLE], EdmType.DOUBLE, allow_numeric_promotion=True))
    
    def register(self, name: str, func: Callable, signature: FunctionSignature):
        """
        Register a function.
        
        Args:
            name: Function name (lowercase)
            func: Function implementation
            signature: Function signature
        """
        self._functions[name.lower()] = (func, signature)
    
    def lookup(self, name: str) -> Optional[tuple[Callable, FunctionSignature]]:
        """
        Look up function by name.
        
        Args:
            name: Function name (case-insensitive)
            
        Returns:
            Tuple of (function, signature) or None if not found
        """
        return self._functions.get(name.lower())
    
    def call(self, name: str, args: list[Any]) -> Any:
        """
        Call function with arguments.
        
        Args:
            name: Function name
            args: Function arguments
            
        Returns:
            Function result
            
        Raises:
            EdmTypeError: If function not found or signature mismatch
        """
        # Special handling for substring (variable arguments)
        if name.lower() == 'substring':
            if len(args) == 2:
                return FunctionLibrary.substring(args[0], args[1])
            elif len(args) == 3:
                return FunctionLibrary.substring(args[0], args[1], args[2])
            else:
                raise EdmTypeError(
                    f"Function 'substring' expects 2 or 3 arguments, got {len(args)}"
                )
        
        # Look up function
        result = self.lookup(name)
        if result is None:
            raise EdmTypeError(f"Unknown function '{name}'")
        
        func, signature = result
        
        # Validate argument count
        if len(args) != len(signature.arg_types):
            raise EdmTypeError(
                f"Function '{name}' expects {len(signature.arg_types)} argument(s), "
                f"got {len(args)}"
            )
        
        # Call function
        return func(*args)
    
    def get_signature(self, name: str) -> Optional[FunctionSignature]:
        """
        Get function signature.
        
        Args:
            name: Function name
            
        Returns:
            Function signature or None if not found
        """
        result = self.lookup(name)
        if result is None:
            return None
        return result[1]
    
    def list_functions(self) -> list[str]:
        """
        List all registered function names.
        
        Returns:
            Sorted list of function names
        """
        return sorted(self._functions.keys())
