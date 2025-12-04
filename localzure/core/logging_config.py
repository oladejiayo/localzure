"""
Logging infrastructure for LocalZure.

Provides structured logging with JSON formatting and sensitive data redaction.
"""

import logging
import logging.handlers
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable for correlation IDs
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log messages."""
    
    # Patterns for sensitive data
    PATTERNS = [
        (re.compile(r'(Authorization:\s+)(?:Bearer\s+)?\S+', re.IGNORECASE), r'\1***REDACTED***'),
        (re.compile(r'(x-ms-encryption-key:\s+)\S+', re.IGNORECASE), r'\1***REDACTED***'),
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)\S+', re.IGNORECASE), r'\1***REDACTED***'),
        (re.compile(r'(AccountKey=)[^;]+', re.IGNORECASE), r'\1***REDACTED***'),
        (re.compile(r'(SharedAccessSignature=)[^;&]+', re.IGNORECASE), r'\1***REDACTED***'),
        (re.compile(r'(sig=)[^;&]+', re.IGNORECASE), r'\1***REDACTED***'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log record."""
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation ID if present
        if corr_id := correlation_id.get():
            log_data["correlation_id"] = corr_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra context if present
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter."""
    
    def __init__(self):
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None,
    rotation_size: str = "10MB",
    rotation_count: int = 5,
    module_levels: Optional[Dict[str, str]] = None
) -> None:
    """
    Configure LocalZure logging infrastructure.
    
    Args:
        level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format ("json" or "text")
        log_file: Optional file path for log output
        rotation_size: Size limit for log rotation (e.g., "10MB")
        rotation_count: Number of rotated log files to keep
        module_levels: Optional dict of module-specific log levels
                      e.g., {"localzure.core.runtime": "DEBUG", "localzure.services": "INFO"}
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)
    
    # File handler with rotation if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse rotation size
        max_bytes = _parse_size(rotation_size)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=rotation_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(file_handler)
        
        root_logger.info(f"Logging to file: {log_file} (rotation: {rotation_size}, count: {rotation_count})")
    
    # Configure module-specific log levels
    if module_levels:
        for module_name, module_level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(getattr(logging, module_level.upper()))
            root_logger.info(f"Module '{module_name}' log level set to {module_level}")
    
    root_logger.info(f"Logging configured: level={level}, format={format_type}")


def _parse_size(size_str: str) -> int:
    """
    Parse size string to bytes.
    
    Args:
        size_str: Size string (e.g., "10MB", "1GB")
    
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    # Check longer suffixes first to avoid matching 'B' in 'MB'
    multipliers = [
        ('GB', 1024 ** 3),
        ('MB', 1024 ** 2),
        ('KB', 1024),
        ('B', 1),
    ]
    
    for suffix, multiplier in multipliers:
        if size_str.endswith(suffix):
            number = size_str[:-len(suffix)].strip()
            return int(float(number) * multiplier)
    
    # Default to bytes if no suffix
    return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_correlation_id(corr_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(corr_id)


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id.set(None)


def log_with_context(logger: logging.Logger, level: int, message: str, **context: Any) -> None:
    """
    Log a message with additional context.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **context: Additional context to include in log
    """
    extra = {"context": context} if context else {}
    logger.log(level, message, extra=extra)
