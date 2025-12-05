"""
Unit Tests for Service Bus Structured Logging

Tests for correlation tracking, structured logging, and log output format.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import asyncio
import json
import logging
import pytest
from io import StringIO
from unittest.mock import patch

from localzure.services.servicebus.logging_utils import (
    CorrelationContext,
    StructuredFormatter,
    StructuredLogger,
    configure_logging,
    track_operation_time,
)


class TestCorrelationContext:
    """Tests for correlation context management."""
    
    def test_get_correlation_id_generates_new(self):
        """Test that get_correlation_id generates new ID if none set."""
        CorrelationContext.clear_correlation_id()
        corr_id = CorrelationContext.get_correlation_id()
        assert corr_id is not None
        assert len(corr_id) == 36  # UUID format
    
    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        test_id = "test-correlation-123"
        CorrelationContext.set_correlation_id(test_id)
        assert CorrelationContext.get_correlation_id() == test_id
    
    def test_clear_correlation_id(self):
        """Test clearing correlation ID."""
        CorrelationContext.set_correlation_id("test-id")
        CorrelationContext.clear_correlation_id()
        # After clear, a new ID should be generated
        new_id = CorrelationContext.get_correlation_id()
        assert new_id != "test-id"


class TestStructuredFormatter:
    """Tests for JSON structured formatter."""
    
    def test_format_basic_record(self):
        """Test formatting basic log record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        log_data = json.loads(output)
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['logger'] == 'test_logger'
        assert 'timestamp' in log_data
        assert 'correlation_id' in log_data
    
    def test_format_with_extra_fields(self):
        """Test formatting with extra context fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Operation completed",
            args=(),
            exc_info=None
        )
        record.operation = "queue_created"
        record.entity_type = "queue"
        record.entity_name = "test-queue"
        record.duration_ms = 15.5
        
        output = formatter.format(record)
        log_data = json.loads(output)
        
        assert log_data['operation'] == 'queue_created'
        assert log_data['entity_type'] == 'queue'
        assert log_data['entity_name'] == 'test-queue'
        assert log_data['duration_ms'] == 15.5
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )
            
            output = formatter.format(record)
            log_data = json.loads(output)
            
            assert 'exception' in log_data
            assert log_data['exception']['type'] == 'ValueError'
            assert 'Test error' in log_data['exception']['message']
            assert 'traceback' in log_data['exception']


class TestStructuredLogger:
    """Tests for structured logger."""
    
    @pytest.fixture
    def logger_with_capture(self):
        """Create logger with captured output."""
        logger = StructuredLogger('test_logger')
        logger.logger.handlers.clear()
        
        # Add string handler to capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)
        
        return logger, stream
    
    def test_debug_logging(self, logger_with_capture):
        """Test debug level logging."""
        logger, stream = logger_with_capture
        
        logger.debug("Debug message", operation="test_op")
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['level'] == 'DEBUG'
        assert log_data['message'] == 'Debug message'
        assert log_data['operation'] == 'test_op'
    
    def test_info_logging(self, logger_with_capture):
        """Test info level logging."""
        logger, stream = logger_with_capture
        
        logger.info("Info message", operation="test_op")
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Info message'
    
    def test_error_logging(self, logger_with_capture):
        """Test error level logging."""
        logger, stream = logger_with_capture
        
        logger.error("Error message", error_type="TestError", error_message="Test error details")
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['level'] == 'ERROR'
        assert log_data['error_type'] == 'TestError'
        assert log_data['error_message'] == 'Test error details'
    
    def test_log_operation(self, logger_with_capture):
        """Test logging entity operations."""
        logger, stream = logger_with_capture
        
        logger.log_operation(
            operation="queue_created",
            entity_type="queue",
            entity_name="test-queue",
            lock_duration=60
        )
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['operation'] == 'queue_created'
        assert log_data['entity_type'] == 'queue'
        assert log_data['entity_name'] == 'test-queue'
        assert log_data['lock_duration'] == 60
    
    def test_log_message_operation(self, logger_with_capture):
        """Test logging message operations."""
        logger, stream = logger_with_capture
        
        logger.log_message_operation(
            operation="message_sent",
            entity_type="queue",
            entity_name="test-queue",
            message_id="msg-123",
            sequence_number=1
        )
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['operation'] == 'message_sent'
        assert log_data['message_id'] == 'msg-123'
        assert log_data['sequence_number'] == 1
    
    def test_log_filter_evaluation(self, logger_with_capture):
        """Test logging filter evaluation."""
        logger, stream = logger_with_capture
        
        logger.log_filter_evaluation(
            filter_expression="priority = 'high'",
            filter_result=True,
            message_id="msg-123",
            subscription_name="sub-1"
        )
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['operation'] == 'filter_evaluated'
        assert log_data['filter_expression'] == "priority = 'high'"
        assert log_data['filter_result'] is True
        assert log_data['subscription_name'] == 'sub-1'
    
    def test_log_lock_operation(self, logger_with_capture):
        """Test logging lock operations."""
        logger, stream = logger_with_capture
        
        logger.log_lock_operation(
            operation="lock_acquired",
            entity_type="queue",
            entity_name="test-queue",
            message_id="msg-123",
            lock_token="lock-token-456"
        )
        
        output = stream.getvalue()
        log_data = json.loads(output)
        
        assert log_data['operation'] == 'lock_acquired'
        assert log_data['message_id'] == 'msg-123'
        assert log_data['lock_token'] == 'lock-token-456'


class TestOperationTimeTracking:
    """Tests for operation time tracking decorator."""
    
    @pytest.mark.asyncio
    async def test_track_successful_operation(self):
        """Test tracking successful async operation."""
        logger = StructuredLogger('test_logger')
        
        @track_operation_time(logger, "test_operation")
        async def test_func():
            await asyncio.sleep(0.01)
            return "success"
        
        result = await test_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_track_failed_operation(self):
        """Test tracking failed async operation."""
        logger = StructuredLogger('test_logger')
        
        @track_operation_time(logger, "test_operation")
        async def test_func():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await test_func()


class TestConfigureLogging:
    """Tests for logging configuration."""
    
    def test_configure_logging_json_format(self):
        """Test configuring logging with JSON format."""
        configure_logging(level="DEBUG", json_format=True)
        
        logger = logging.getLogger('localzure.services.servicebus')
        assert logger.level == logging.DEBUG
    
    def test_configure_logging_plain_format(self):
        """Test configuring logging with plain text format."""
        configure_logging(level="INFO", json_format=False)
        
        logger = logging.getLogger('localzure.services.servicebus')
        assert logger.level == logging.INFO
    
    def test_configure_logging_different_levels(self):
        """Test configuring different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            configure_logging(level=level)
            logger = logging.getLogger('localzure.services.servicebus')
            assert logger.level == getattr(logging, level)
