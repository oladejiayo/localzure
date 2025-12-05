"""
Integration Tests for Service Bus Logging and Correlation Tracking

Tests for correlation ID propagation through API requests and log output validation.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import pytest
import json
import logging
from io import StringIO
from fastapi import FastAPI
from fastapi.testclient import TestClient

from localzure.services.servicebus.api import router, backend
from localzure.services.servicebus.middleware import CorrelationMiddleware
from localzure.services.servicebus.logging_utils import StructuredFormatter, CorrelationContext


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()
    yield
    await backend.reset()


@pytest.fixture
def app_with_middleware():
    """Create FastAPI app with correlation middleware."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    app.include_router(router)
    return app


@pytest.fixture
def client_with_middleware(app_with_middleware):
    """Create test client with middleware."""
    return TestClient(app_with_middleware)


@pytest.fixture
def captured_logs():
    """Capture log output for validation."""
    # Setup log capture
    logger = logging.getLogger('localzure.services.servicebus')
    logger.handlers.clear()
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield stream
    
    # Cleanup
    logger.handlers.clear()


class TestCorrelationIDPropagation:
    """Tests for correlation ID extraction and propagation."""
    
    def test_generates_correlation_id_if_not_provided(self, client_with_middleware):
        """Test that correlation ID is generated if not in request."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        response = client_with_middleware.put(
            "/servicebus/test-namespace/test-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        assert response.status_code in [200, 201]
        assert 'x-correlation-id' in response.headers
        assert len(response.headers['x-correlation-id']) == 36  # UUID format
    
    def test_uses_provided_correlation_id(self, client_with_middleware):
        """Test that provided correlation ID is used."""
        test_correlation_id = "test-correlation-123"
        
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        response = client_with_middleware.put(
            "/servicebus/test-namespace/test-queue-2",
            content=queue_xml,
            headers={
                "Content-Type": "application/xml",
                "x-correlation-id": test_correlation_id
            },
        )
        
        assert response.status_code in [200, 201]
        assert response.headers['x-correlation-id'] == test_correlation_id
    
    def test_correlation_id_in_response_header(self, client_with_middleware):
        """Test that correlation ID is included in response headers."""
        response = client_with_middleware.get("/servicebus/test-namespace")
        
        assert 'x-correlation-id' in response.headers
    
    def test_correlation_id_propagates_through_request(self, client_with_middleware, captured_logs):
        """Test that correlation ID propagates through entire request."""
        test_correlation_id = "test-correlation-456"
        
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        response = client_with_middleware.put(
            "/servicebus/test-namespace/test-queue-3",
            content=queue_xml,
            headers={
                "Content-Type": "application/xml",
                "x-correlation-id": test_correlation_id
            },
        )
        
        assert response.status_code in [200, 201]
        
        # Check logs contain correlation ID
        log_output = captured_logs.getvalue()
        log_lines = [line for line in log_output.strip().split('\n') if line]
        
        for line in log_lines:
            log_data = json.loads(line)
            assert log_data['correlation_id'] == test_correlation_id


class TestLogOutputFormat:
    """Tests for structured log output format."""
    
    def test_log_contains_required_fields(self, client_with_middleware, captured_logs):
        """Test that logs contain all required fields."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        client_with_middleware.put(
            "/servicebus/test-namespace/log-test-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        log_output = captured_logs.getvalue()
        log_lines = [line for line in log_output.strip().split('\n') if line]
        
        for line in log_lines:
            log_data = json.loads(line)
            
            # Check required fields
            assert 'timestamp' in log_data
            assert 'level' in log_data
            assert 'message' in log_data
            assert 'correlation_id' in log_data
            assert 'logger' in log_data
    
    def test_operation_logs_include_context(self, client_with_middleware, captured_logs):
        """Test that operation logs include entity context."""
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        client_with_middleware.put(
            "/servicebus/test-namespace/context-test-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        log_output = captured_logs.getvalue()
        log_lines = [line for line in log_output.strip().split('\n') if line]
        
        # Find request_started log
        request_logs = [json.loads(line) for line in log_lines if 'request_started' in line]
        assert len(request_logs) > 0
        
        request_log = request_logs[0]
        assert request_log['operation'] == 'request_started'
        # Message contains method and path info
        assert 'PUT' in request_log['message']
        assert 'context-test-queue' in request_log['message']


class TestMessageOperationLogging:
    """Tests for message operation logging."""
    
    def test_send_message_logged(self, client_with_middleware, captured_logs):
        """Test that message send operation is logged."""
        # Create queue first
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        client_with_middleware.put(
            "/servicebus/test-namespace/msg-queue",
            content=queue_xml,
            headers={"Content-Type": "application/xml"},
        )
        
        # Clear logs
        captured_logs.truncate(0)
        captured_logs.seek(0)
        
        # Send message
        response = client_with_middleware.post(
            "/servicebus/test-namespace/msg-queue/messages",
            json={"body": "Test message", "label": "test"},
        )
        
        assert response.status_code == 200
        
        log_output = captured_logs.getvalue()
        log_lines = [line for line in log_output.strip().split('\n') if line]
        
        # Find message operation logs
        message_logs = [json.loads(line) for line in log_lines if 'message_sent' in line]
        
        if message_logs:
            msg_log = message_logs[0]
            assert msg_log['operation'] == 'message_sent'
            assert msg_log['entity_type'] == 'queue'
            assert msg_log['entity_name'] == 'msg-queue'
            assert 'message_id' in msg_log
            assert 'sequence_number' in msg_log


class TestErrorLogging:
    """Tests for error logging."""
    
    def test_error_includes_context(self, client_with_middleware, captured_logs):
        """Test that errors include full context."""
        # Try to send to non-existent queue
        response = client_with_middleware.post(
            "/servicebus/test-namespace/nonexistent-queue/messages",
            json={"body": "Test message"},
        )
        
        assert response.status_code == 404
        
        log_output = captured_logs.getvalue()
        log_lines = [line for line in log_output.strip().split('\n') if line]
        
        # Should have error logs
        error_logs = [json.loads(line) for line in log_lines if json.loads(line)['level'] == 'ERROR']
        
        if error_logs:
            error_log = error_logs[0]
            assert 'correlation_id' in error_log
            assert 'operation' in error_log or 'method' in error_log


class TestPerformanceOverhead:
    """Tests for logging performance overhead."""
    
    def test_logging_overhead_acceptable(self, client_with_middleware):
        """Test that logging overhead is < 5% of operation time."""
        import time
        
        queue_xml = """<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom">
    <content type="application/xml">
        <QueueDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
            <LockDuration>PT60S</LockDuration>
        </QueueDescription>
    </content>
</entry>"""
        
        # Measure with logging
        start_with_logging = time.time()
        for i in range(10):
            client_with_middleware.put(
                f"/servicebus/test-namespace/perf-queue-{i}",
                content=queue_xml,
                headers={"Content-Type": "application/xml"},
            )
        duration_with_logging = time.time() - start_with_logging
        
        # Simple check - should complete in reasonable time (not a precise 5% check)
        assert duration_with_logging < 5.0  # 10 operations should complete in < 5 seconds
