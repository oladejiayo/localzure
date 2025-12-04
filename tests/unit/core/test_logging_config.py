"""
Tests for logging infrastructure.
"""

import logging
import json
import tempfile
from pathlib import Path

import pytest

from localzure.core.logging_config import (
    setup_logging,
    get_logger,
    set_correlation_id,
    clear_correlation_id,
    log_with_context,
    JSONFormatter,
    SensitiveDataFilter,
    _parse_size
)


class TestLoggingSetup:
    """Test suite for logging setup."""
    
    def test_setup_logging_defaults(self):
        """Test setting up logging with defaults."""
        setup_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0
    
    def test_setup_logging_with_level(self):
        """Test setting up logging with custom level."""
        setup_logging(level="DEBUG")
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
    
    def test_setup_logging_with_file(self, tmp_path):
        """Test setting up logging with file output."""
        log_file = tmp_path / "test.log"
        setup_logging(log_file=str(log_file))
        
        logger = get_logger(__name__)
        logger.info("Test message")
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content
    
    def test_get_logger(self):
        """Test getting a logger instance."""
        logger = get_logger("test.module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
    
    def test_setup_logging_with_module_levels(self):
        """Test setting up logging with per-module log levels."""
        setup_logging(
            level="INFO",
            module_levels={
                "test.module.debug": "DEBUG",
                "test.module.error": "ERROR"
            }
        )
        
        # Check root logger is INFO
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        
        # Check module-specific levels
        debug_logger = logging.getLogger("test.module.debug")
        assert debug_logger.level == logging.DEBUG
        
        error_logger = logging.getLogger("test.module.error")
        assert error_logger.level == logging.ERROR
    
    def test_module_level_filtering(self):
        """Test that module-specific levels filter messages correctly."""
        setup_logging(
            level="INFO",
            module_levels={"test.debug_module": "DEBUG"}
        )
        
        # Logger with DEBUG level should log DEBUG messages
        debug_logger = get_logger("test.debug_module")
        assert debug_logger.isEnabledFor(logging.DEBUG)
        
        # Logger with default INFO should not log DEBUG
        info_logger = get_logger("test.info_module")
        assert not info_logger.isEnabledFor(logging.DEBUG)
        assert info_logger.isEnabledFor(logging.INFO)


class TestJSONFormatter:
    """Test suite for JSON formatter."""
    
    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "INFO"
        assert data["module"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data
    
    def test_format_with_correlation_id(self):
        """Test formatting with correlation ID."""
        set_correlation_id("test-correlation-id")
        
        try:
            formatter = JSONFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            output = formatter.format(record)
            data = json.loads(output)
            
            assert data["correlation_id"] == "test-correlation-id"
        finally:
            clear_correlation_id()
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )
            
            output = formatter.format(record)
            data = json.loads(output)
            
            assert "exception" in data
            assert "ValueError" in data["exception"]
            assert "Test error" in data["exception"]


class TestSensitiveDataFilter:
    """Test suite for sensitive data filter."""
    
    def test_redact_authorization_header(self):
        """Test redacting Authorization header."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Authorization: Bearer secret_token_here",
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert "secret_token_here" not in record.msg
        assert "***REDACTED***" in record.msg
    
    def test_redact_encryption_key(self):
        """Test redacting encryption key."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="x-ms-encryption-key: base64encodedkey",
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert "base64encodedkey" not in record.msg
        assert "***REDACTED***" in record.msg
    
    def test_redact_password(self):
        """Test redacting password."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='password="secret123"',
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert "secret123" not in record.msg
        assert "***REDACTED***" in record.msg
    
    def test_redact_account_key(self):
        """Test redacting account key from connection string."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=secretkey123;",
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert "secretkey123" not in record.msg
        assert "***REDACTED***" in record.msg
    
    def test_redact_sas_signature(self):
        """Test redacting SAS signature."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="?sig=base64signature&se=2025-12-31",
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert "base64signature" not in record.msg
        assert "***REDACTED***" in record.msg


class TestCorrelationId:
    """Test suite for correlation ID management."""
    
    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        from localzure.core.logging_config import correlation_id
        
        set_correlation_id("test-id-123")
        assert correlation_id.get() == "test-id-123"
        
        clear_correlation_id()
        assert correlation_id.get() is None
    
    def test_log_with_context(self):
        """Test logging with context."""
        setup_logging(format_type="json")
        logger = get_logger("test")
        
        # This primarily tests that the function doesn't error
        log_with_context(
            logger,
            logging.INFO,
            "Test message",
            user_id="user123",
            request_id="req456"
        )


class TestParsizeSize:
    """Test suite for size parsing."""
    
    def test_parse_bytes(self):
        """Test parsing bytes."""
        assert _parse_size("100") == 100
        assert _parse_size("100B") == 100
    
    def test_parse_kilobytes(self):
        """Test parsing kilobytes."""
        assert _parse_size("1KB") == 1024
        assert _parse_size("10KB") == 10240
    
    def test_parse_megabytes(self):
        """Test parsing megabytes."""
        assert _parse_size("1MB") == 1048576
        assert _parse_size("10MB") == 10485760
    
    def test_parse_gigabytes(self):
        """Test parsing gigabytes."""
        assert _parse_size("1GB") == 1073741824
    
    def test_parse_lowercase(self):
        """Test parsing with lowercase units."""
        assert _parse_size("1mb") == 1048576
        assert _parse_size("5kb") == 5120
    
    def test_parse_with_whitespace(self):
        """Test parsing with whitespace."""
        assert _parse_size(" 10 MB ") == 10485760
    
    def test_parse_decimal(self):
        """Test parsing decimal values."""
        assert _parse_size("1.5MB") == int(1.5 * 1048576)
