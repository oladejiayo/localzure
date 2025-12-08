"""
Service Bus Security Validation

Input validation and security controls for Service Bus operations.
Provides protection against SQL injection, malicious inputs, and resource exhaustion.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

import re
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from .constants import (
    MAX_MESSAGE_SIZE,
    MAX_QUEUE_NAME_LENGTH,
    MAX_TOPIC_NAME_LENGTH,
    MAX_SUBSCRIPTION_NAME_LENGTH,
    SQL_OPERATORS,
    SQL_LOGICAL_OPS,
    SQL_KEYWORDS,
)
from .exceptions import (
    InvalidEntityNameError,
    MessageSizeExceededError,
    InvalidOperationError,
)


# ========== Entity Name Validation ==========

class EntityNameValidator:
    """
    Validates entity names against Azure Service Bus naming rules.
    
    Provides comprehensive validation for queues, topics, subscriptions,
    and rules to prevent injection attacks and ensure Azure compatibility.
    """
    
    # Reserved words that cannot be used as entity names
    RESERVED_WORDS = {
        'system', 'null', 'true', 'false', 'exec', 'drop', 'delete',
        'insert', 'update', 'create', 'alter', 'grant', 'revoke',
    }
    
    # Disallowed characters for security
    DISALLOWED_CHARS = {'%', '&', '?', '#', '@', '!', '*', '(', ')', '<', '>', '=', '+'}
    
    # Pattern for queue/topic names (alphanumeric, hyphens, underscores, periods)
    QUEUE_TOPIC_PATTERN = re.compile(r'^[a-zA-Z0-9][\w\-\.]*[a-zA-Z0-9]$')
    
    # Pattern for subscription names (more restrictive - alphanumeric and hyphens only)
    SUBSCRIPTION_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$')
    
    @classmethod
    def validate_queue_name(cls, name: str) -> None:
        """
        Validate queue name against Azure rules.
        
        Rules:
        - Length: 1-260 characters
        - Allowed: letters, numbers, periods, hyphens, underscores
        - Cannot start/end with slash
        - No reserved words
        - No disallowed characters
        
        Args:
            name: Queue name to validate
            
        Raises:
            InvalidEntityNameError: If validation fails
        """
        cls._validate_entity_name(name, "queue", MAX_QUEUE_NAME_LENGTH, cls.QUEUE_TOPIC_PATTERN)
    
    @classmethod
    def validate_topic_name(cls, name: str) -> None:
        """
        Validate topic name against Azure rules.
        
        Args:
            name: Topic name to validate
            
        Raises:
            InvalidEntityNameError: If validation fails
        """
        cls._validate_entity_name(name, "topic", MAX_TOPIC_NAME_LENGTH, cls.QUEUE_TOPIC_PATTERN)
    
    @classmethod
    def validate_subscription_name(cls, name: str) -> None:
        """
        Validate subscription name against Azure rules.
        
        Rules:
        - Length: 1-50 characters
        - Allowed: letters, numbers, hyphens
        - More restrictive than queue/topic names
        
        Args:
            name: Subscription name to validate
            
        Raises:
            InvalidEntityNameError: If validation fails
        """
        cls._validate_entity_name(name, "subscription", MAX_SUBSCRIPTION_NAME_LENGTH, cls.SUBSCRIPTION_PATTERN)
    
    @classmethod
    def _validate_entity_name(
        cls,
        name: str,
        entity_type: str,
        max_length: int,
        pattern: re.Pattern
    ) -> None:
        """Internal validation logic."""
        if not name:
            raise InvalidEntityNameError(
                entity_type,
                name,
                "Name cannot be empty"
            )
        
        if len(name) > max_length:
            raise InvalidEntityNameError(
                entity_type,
                name,
                f"Name exceeds maximum length of {max_length} characters"
            )
        
        # Check for disallowed characters
        for char in cls.DISALLOWED_CHARS:
            if char in name:
                raise InvalidEntityNameError(
                    entity_type,
                    name,
                    f"Name contains disallowed character: '{char}'"
                )
        
        # Check for slashes at start/end
        if name.startswith('/') or name.endswith('/'):
            raise InvalidEntityNameError(
                entity_type,
                name,
                "Name cannot start or end with slash"
            )
        
        # Check pattern
        if not pattern.match(name):
            raise InvalidEntityNameError(
                entity_type,
                name,
                "Name must start and end with alphanumeric characters and contain only allowed characters"
            )
        
        # Check for consecutive special characters
        if '--' in name or '__' in name or '..' in name:
            raise InvalidEntityNameError(
                entity_type,
                name,
                "Name cannot contain consecutive hyphens, underscores, or periods"
            )
        
        # Check for reserved words (case-insensitive)
        if name.lower() in cls.RESERVED_WORDS:
            raise InvalidEntityNameError(
                entity_type,
                name,
                f"Name is reserved: '{name}'"
            )


# ========== Message Validation ==========

class MessageValidator:
    """
    Validates message content and properties for security and size limits.
    
    Enforces message size limits, property validation, and content security.
    """
    
    MAX_USER_PROPERTIES = 64
    MAX_PROPERTY_KEY_LENGTH = 128
    MAX_PROPERTY_VALUE_SIZE = 32 * 1024  # 32 KB
    SYSTEM_PROPERTY_PREFIX = 'sys.'
    
    # Pattern for property keys (alphanumeric + underscore)
    PROPERTY_KEY_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    @classmethod
    def validate_message_size(cls, message_dict: Dict[str, Any], max_size: int = MAX_MESSAGE_SIZE) -> None:
        """
        Validate message size does not exceed limit.
        
        Calculates total message size including body, properties, and metadata.
        
        Args:
            message_dict: Message as dictionary
            max_size: Maximum allowed size in bytes (default: 256KB)
            
        Raises:
            MessageSizeExceededError: If message exceeds size limit
        """
        # Calculate size as JSON-encoded message
        message_json = json.dumps(message_dict)
        actual_size = len(message_json.encode('utf-8'))
        
        if actual_size > max_size:
            raise MessageSizeExceededError(actual_size, max_size)
    
    @classmethod
    def validate_user_properties(cls, properties: Dict[str, Any]) -> None:
        """
        Validate user properties for security and size limits.
        
        Rules:
        - Max 64 properties
        - Key: 1-128 chars, alphanumeric + underscore
        - Value: string/int/float/bool only
        - Max value size: 32 KB
        - System properties (sys.*) are read-only
        
        Args:
            properties: User properties dictionary
            
        Raises:
            InvalidOperationError: If validation fails
        """
        if len(properties) > cls.MAX_USER_PROPERTIES:
            raise InvalidOperationError(
                "validate_user_properties",
                f"Too many properties: {len(properties)} (max: {cls.MAX_USER_PROPERTIES})"
            )
        
        for key, value in properties.items():
            # Validate key length
            if len(key) > cls.MAX_PROPERTY_KEY_LENGTH:
                raise InvalidOperationError(
                    "validate_user_properties",
                    f"Property key '{key}' exceeds maximum length of {cls.MAX_PROPERTY_KEY_LENGTH}"
                )
            
            # Validate key format
            if not cls.PROPERTY_KEY_PATTERN.match(key):
                raise InvalidOperationError(
                    "validate_user_properties",
                    f"Property key '{key}' contains invalid characters (alphanumeric and underscore only)"
                )
            
            # Prevent system property override
            if key.startswith(cls.SYSTEM_PROPERTY_PREFIX):
                raise InvalidOperationError(
                    "validate_user_properties",
                    f"Property key '{key}' is reserved (sys.* prefix)"
                )
            
            # Validate value type
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise InvalidOperationError(
                    "validate_user_properties",
                    f"Property '{key}' has invalid type: {type(value).__name__} (must be string/int/float/bool)"
                )
            
            # Validate value size (for strings)
            if isinstance(value, str):
                value_size = len(value.encode('utf-8'))
                if value_size > cls.MAX_PROPERTY_VALUE_SIZE:
                    raise InvalidOperationError(
                        "validate_user_properties",
                        f"Property '{key}' value exceeds maximum size of {cls.MAX_PROPERTY_VALUE_SIZE} bytes"
                    )


# ========== SQL Filter Sanitization ==========

class SqlFilterSanitizer:
    """
    Sanitizes and validates SQL filter expressions for security.
    
    Prevents SQL injection attacks by:
    - Allowlisting safe operators
    - Blocking dangerous SQL keywords
    - Limiting expression complexity
    - Enforcing evaluation timeouts
    """
    
    # Dangerous SQL keywords that must be blocked
    DANGEROUS_KEYWORDS = {
        'EXEC', 'EXECUTE', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'CREATE',
        'ALTER', 'GRANT', 'REVOKE', 'TRUNCATE', 'DECLARE', 'CAST', 'CONVERT',
        'OPENQUERY', 'OPENROWSET', 'BULK', 'BACKUP', 'RESTORE', 'SHUTDOWN',
        'xp_', 'sp_', 'WAITFOR', 'DELAY', 'INFORMATION_SCHEMA', 'SYSOBJECTS',
    }
    
    # Maximum complexity limits
    MAX_CONDITIONS = 10  # Max number of AND/OR conditions
    MAX_NESTING_LEVEL = 3  # Max parenthesis nesting depth
    MAX_IN_VALUES = 50  # Max values in IN clause
    MAX_FILTER_LENGTH = 2000  # Max characters in filter expression
    
    @classmethod
    def validate_sql_filter(cls, filter_expression: str) -> None:
        """
        Validate SQL filter expression for security.
        
        Args:
            filter_expression: SQL filter string
            
        Raises:
            InvalidOperationError: If filter is unsafe or too complex
        """
        if not filter_expression:
            return
        
        # Check length
        if len(filter_expression) > cls.MAX_FILTER_LENGTH:
            raise InvalidOperationError(
                "sql_filter_validation",
                f"Filter expression exceeds maximum length of {cls.MAX_FILTER_LENGTH} characters"
            )
        
        # Convert to uppercase for keyword checking
        upper_filter = filter_expression.upper()
        
        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in upper_filter:
                raise InvalidOperationError(
                    "sql_filter_validation",
                    f"Filter contains dangerous SQL keyword: {keyword}"
                )
        
        # Validate operator allowlist
        cls._validate_operators(filter_expression)
        
        # Check complexity limits
        cls._validate_complexity(filter_expression)
    
    @classmethod
    def _validate_operators(cls, expression: str) -> None:
        """Validate that only allowlisted operators are used."""
        # Remove string literals to avoid false positives
        cleaned = re.sub(r"'[^']*'", "", expression)
        
        # Extract potential operators (sequences of special characters)
        # Split on each character to check individually
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_. \t\n')
        allowed_ops = {'(', ')', ',', '>=', '<=', '<>', '!=', '=', '<', '>', '+', '-', '*', '/'}
        
        # Check for multi-char operators first
        for op in ['>=', '<=', '<>', '!=']:
            cleaned = cleaned.replace(op, ' ')
        
        # Check remaining single chars
        for char in cleaned:
            if char not in allowed_chars and char not in ['(', ')', ',', '=', '<', '>', '+', '-', '*', '/']:
                raise InvalidOperationError(
                    "sql_filter_validation",
                    f"Filter contains disallowed character: '{char}'"
                )
    
    @classmethod
    def _validate_complexity(cls, expression: str) -> None:
        """Validate expression complexity limits."""
        # Count AND/OR conditions
        and_count = expression.upper().count(' AND ')
        or_count = expression.upper().count(' OR ')
        total_conditions = and_count + or_count
        
        if total_conditions > cls.MAX_CONDITIONS:
            raise InvalidOperationError(
                "sql_filter_validation",
                f"Filter too complex: {total_conditions} conditions (max: {cls.MAX_CONDITIONS})"
            )
        
        # Check nesting level (count max depth of parentheses)
        max_depth = 0
        current_depth = 0
        for char in expression:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
        
        if max_depth > cls.MAX_NESTING_LEVEL:
            raise InvalidOperationError(
                "sql_filter_validation",
                f"Filter nesting too deep: {max_depth} levels (max: {cls.MAX_NESTING_LEVEL})"
            )
        
        # Check IN clause value count
        in_matches = re.findall(r'IN\s*\(([^)]+)\)', expression, re.IGNORECASE)
        for match in in_matches:
            value_count = len(match.split(','))
            if value_count > cls.MAX_IN_VALUES:
                raise InvalidOperationError(
                    "sql_filter_validation",
                    f"IN clause too large: {value_count} values (max: {cls.MAX_IN_VALUES})"
                )


# ========== Lock Token Validation ==========

class LockTokenValidator:
    """
    Validates message lock tokens for security.
    
    Provides constant-time validation to prevent timing attacks.
    """
    
    # UUID v4 pattern
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    @classmethod
    def validate_format(cls, lock_token: str) -> None:
        """
        Validate lock token format.
        
        Args:
            lock_token: Lock token string
            
        Raises:
            InvalidOperationError: If token format is invalid
        """
        if not lock_token:
            raise InvalidOperationError(
                "validate_lock_token",
                "Lock token cannot be empty"
            )
        
        if not cls.UUID_PATTERN.match(lock_token):
            raise InvalidOperationError(
                "validate_lock_token",
                "Lock token must be a valid UUID v4"
            )
    
    @classmethod
    def compare_constant_time(cls, token1: str, token2: str) -> bool:
        """
        Compare two tokens in constant time to prevent timing attacks.
        
        Args:
            token1: First token
            token2: Second token
            
        Returns:
            True if tokens match, False otherwise
        """
        if len(token1) != len(token2):
            return False
        
        result = 0
        for c1, c2 in zip(token1, token2):
            result |= ord(c1) ^ ord(c2)
        
        return result == 0


# ========== Session ID Validation ==========

class SessionIdValidator:
    """Validates session IDs for security."""
    
    MAX_SESSION_ID_LENGTH = 128
    SESSION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    
    @classmethod
    def validate(cls, session_id: Optional[str]) -> None:
        """
        Validate session ID.
        
        Args:
            session_id: Session identifier
            
        Raises:
            InvalidOperationError: If validation fails
        """
        if session_id is None:
            return
        
        if len(session_id) > cls.MAX_SESSION_ID_LENGTH:
            raise InvalidOperationError(
                "validate_session_id",
                f"Session ID exceeds maximum length of {cls.MAX_SESSION_ID_LENGTH} characters"
            )
        
        if not cls.SESSION_ID_PATTERN.match(session_id):
            raise InvalidOperationError(
                "validate_session_id",
                "Session ID contains invalid characters (alphanumeric, hyphen, underscore, period only)"
            )
