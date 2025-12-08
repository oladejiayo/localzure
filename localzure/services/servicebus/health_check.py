"""
Service Bus Health Checks

Health check endpoints for Kubernetes readiness and liveness probes.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
from enum import Enum

from .backend import ServiceBusBackend
from .exceptions import ServiceBusError


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceBusHealthCheck:
    """
    Health check provider for Service Bus service.
    
    Implements Kubernetes-compatible readiness, liveness, and overall health checks.
    """
    
    def __init__(self, backend: ServiceBusBackend):
        """
        Initialize health check provider.
        
        Args:
            backend: Service Bus backend instance
        """
        self.backend = backend
        self.start_time = datetime.now(timezone.utc)
        self._last_check_time: Optional[datetime] = None
        self._last_check_status: Optional[HealthStatus] = None
        self._consecutive_failures = 0
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.
        
        Returns:
            Health status dictionary with status, version, uptime, dependencies
        """
        now = datetime.now(timezone.utc)
        uptime_seconds = (now - self.start_time).total_seconds()
        
        # Check if backend exists
        if not self.backend:
            self._consecutive_failures = 999  # Force unhealthy
            self._last_check_time = now
            self._last_check_status = HealthStatus.UNHEALTHY
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "timestamp": now.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "version": "1.0.0",
                "checks": {
                    "storage": {
                        "status": "unhealthy",
                        "message": "Backend not initialized"
                    },
                    "backend": {
                        "status": "unhealthy",
                        "message": "Backend not initialized"
                    }
                }
            }
        
        # Check storage dependency
        storage_healthy = await self._check_storage_health()
        
        # Determine overall status
        if storage_healthy:
            status = HealthStatus.HEALTHY
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                status = HealthStatus.UNHEALTHY
            else:
                status = HealthStatus.DEGRADED
        
        self._last_check_time = now
        self._last_check_status = status
        
        return {
            "status": status.value,
            "timestamp": now.isoformat(),
            "uptime_seconds": int(uptime_seconds),
            "version": "1.0.0",
            "checks": {
                "storage": {
                    "status": "healthy" if storage_healthy else "unhealthy",
                    "message": "Storage is accessible" if storage_healthy else "Storage check failed"
                },
                "backend": {
                    "status": "healthy" if self.backend else "unhealthy",
                    "message": "Backend is initialized" if self.backend else "Backend not initialized"
                }
            }
        }
    
    async def is_ready(self) -> bool:
        """
        Check if service is ready to accept traffic (readiness probe).
        
        Verifies that:
        - Backend is initialized
        - Storage is accessible
        - Service can perform basic operations
        
        Returns:
            True if service is ready, False otherwise
        """
        if not self.backend:
            return False
        
        # Check if storage is accessible
        storage_healthy = await self._check_storage_health()
        if not storage_healthy:
            return False
        
        # Check if we can list queues (basic operation test)
        try:
            await asyncio.wait_for(
                self.backend.list_queues(),
                timeout=2.0
            )
            return True
        except (asyncio.TimeoutError, ServiceBusError, Exception):
            return False
    
    async def is_alive(self) -> bool:
        """
        Check if service is alive and responsive (liveness probe).
        
        Simple check that service can respond to requests.
        Does not check dependencies - just internal responsiveness.
        
        Returns:
            True if service is alive, False otherwise
        """
        if not self.backend:
            return False
        
        # Simple check - if backend exists and we can access it, we're alive
        try:
            # Just verify we can access backend state without I/O
            _ = hasattr(self.backend, '_queues')
            return True
        except Exception:
            return False
    
    async def _check_storage_health(self) -> bool:
        """
        Check if storage backend is healthy.
        
        Returns:
            True if storage is accessible, False otherwise
        """
        try:
            # Try to access storage with timeout
            if not self.backend:
                return False
            
            # Quick check - can we access the storage dicts
            _ = self.backend._queues
            _ = self.backend._topics
            return True
        except Exception:
            return False
    
    def get_uptime(self) -> float:
        """
        Get service uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        now = datetime.now(timezone.utc)
        return (now - self.start_time).total_seconds()
    
    def get_last_check_status(self) -> Optional[HealthStatus]:
        """
        Get status from last health check.
        
        Returns:
            Last health status or None if no check performed
        """
        return self._last_check_status
    
    def get_last_check_time(self) -> Optional[datetime]:
        """
        Get timestamp of last health check.
        
        Returns:
            Last check timestamp or None if no check performed
        """
        return self._last_check_time
    
    def reset_failure_count(self) -> None:
        """Reset consecutive failure counter (for testing)."""
        self._consecutive_failures = 0


# Global health check instance
_health_check: Optional[ServiceBusHealthCheck] = None


def init_health_check(backend: ServiceBusBackend) -> ServiceBusHealthCheck:
    """
    Initialize global health check instance.
    
    Args:
        backend: Service Bus backend instance
        
    Returns:
        ServiceBusHealthCheck instance
    """
    global _health_check
    _health_check = ServiceBusHealthCheck(backend)
    return _health_check


def get_health_check() -> Optional[ServiceBusHealthCheck]:
    """
    Get global health check instance.
    
    Returns:
        ServiceBusHealthCheck instance or None if not initialized
    """
    return _health_check


def reset_health_check() -> None:
    """Reset global health check instance (for testing)."""
    global _health_check
    _health_check = None
