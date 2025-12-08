"""
Service Bus Constants

Centralized constants for error messages, XML declarations, and configuration values.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

# Error message templates
ERROR_QUEUE_NOT_FOUND = "Queue '{name}' not found"
ERROR_QUEUE_ALREADY_EXISTS = "Queue '{name}' already exists"
ERROR_TOPIC_NOT_FOUND = "Topic '{name}' not found"
ERROR_TOPIC_ALREADY_EXISTS = "Topic '{name}' already exists"
ERROR_SUBSCRIPTION_NOT_FOUND = "Subscription '{name}' not found on topic '{topic}'"
ERROR_SUBSCRIPTION_ALREADY_EXISTS = "Subscription '{name}' already exists on topic '{topic}'"
ERROR_RULE_NOT_FOUND = "Rule '{name}' not found on subscription '{subscription}'"
ERROR_RULE_ALREADY_EXISTS = "Rule '{name}' already exists on subscription '{subscription}'"
ERROR_MESSAGE_NOT_FOUND = "Message not found"
ERROR_MESSAGE_LOCK_LOST = "Message lock lost"
ERROR_MESSAGE_SIZE_EXCEEDED = "Message size exceeds 256KB limit"
ERROR_INVALID_QUEUE_NAME = "Invalid queue name: {name}"
ERROR_QUOTA_EXCEEDED = "Quota exceeded: {quota_type}"
ERROR_SESSION_NOT_FOUND = "Session '{session_id}' not found"
ERROR_SESSION_LOCK_LOST = "Session lock lost for '{session_id}'"
ERROR_INVALID_OPERATION = "Invalid operation: {operation}"

# XML constants
XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'
XML_NAMESPACE_I = 'xmlns:i="http://www.w3.org/2001/XMLSchema-instance"'
XML_NAMESPACE_ATOM = 'xmlns="http://www.w3.org/2005/Atom"'
XML_NAMESPACE_SERVICEBUS = 'xmlns:sb="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect"'
XML_MEDIA_TYPE = "application/xml"
XML_MEDIA_TYPE_ATOM = "application/atom+xml"

# Timeout defaults (seconds)
DEFAULT_SEND_TIMEOUT = 30
DEFAULT_RECEIVE_TIMEOUT = 60
DEFAULT_ADMIN_TIMEOUT = 30
DEFAULT_LOCK_DURATION = 60
DEFAULT_MESSAGE_TTL = 1209600  # 14 days

# Size limits
MAX_MESSAGE_SIZE = 256 * 1024  # 256 KB
MAX_QUEUE_NAME_LENGTH = 260
MAX_TOPIC_NAME_LENGTH = 260
MAX_SUBSCRIPTION_NAME_LENGTH = 50

# Quota limits
MAX_QUEUES = 100
MAX_TOPICS = 100
MAX_SUBSCRIPTIONS_PER_TOPIC = 2000
MAX_RULES_PER_SUBSCRIPTION = 100

# SQL Filter operators
SQL_OPERATORS = ['>=', '<=', '<>', '!=', '=', '<', '>']
SQL_LOGICAL_OPS = ['OR', 'AND']
SQL_KEYWORDS = ['IN', 'IS', 'NULL', 'NOT']
