"""
LocalZure Lifecycle Manager.

Manages graceful shutdown, signal handling, request tracking, and startup rollback.
Ensures clean shutdown with configurable timeout and proper cleanup.
"""

import asyncio
import signal
import time
from typing import Optional, Dict, Any, Set, Callable
from enum import Enum
from datetime import datetime, timezone

from .logging_config import get_logger

logger = get_logger(__name__)


class LifecycleState(str, Enum):
    """Runtime lifecycle states."""
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"  # Accepting no new requests, finishing in-flight
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class ShutdownReason(str, Enum):
    """Reasons for shutdown."""
    SIGNAL = "signal"
    MANUAL = "manual"
    ERROR = "error"
    TIMEOUT = "timeout"


class RequestTracker:
    """Track in-flight requests during graceful shutdown."""
    
    def __init__(self):
        self._in_flight: Set[str] = set()
        self._lock = asyncio.Lock()
        self._drain_event = asyncio.Event()
        self._drain_event.set()  # Initially not draining
    
    async def start_request(self, request_id: str) -> bool:
        """
        Register a new request.
        
        Args:
            request_id: Unique request identifier
        
        Returns:
            True if request was registered, False if draining
        """
        async with self._lock:
            if not self._drain_event.is_set():
                return False  # Rejecting new requests during drain
            self._in_flight.add(request_id)
            logger.debug(f"Request {request_id} started, in-flight: {len(self._in_flight)}")
            return True
    
    async def end_request(self, request_id: str) -> None:
        """
        Unregister a completed request.
        
        Args:
            request_id: Unique request identifier
        """
        async with self._lock:
            self._in_flight.discard(request_id)
            logger.debug(f"Request {request_id} ended, in-flight: {len(self._in_flight)}")
    
    async def start_draining(self) -> None:
        """Start draining mode - reject new requests."""
        async with self._lock:
            self._drain_event.clear()
            logger.info(f"Started draining mode, {len(self._in_flight)} requests in-flight")
    
    def get_in_flight_count(self) -> int:
        """Get number of in-flight requests."""
        return len(self._in_flight)
    
    async def wait_for_drain(self, timeout: float) -> bool:
        """
        Wait for all in-flight requests to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if all requests completed, False if timeout
        """
        start_time = time.time()
        
        while len(self._in_flight) > 0:
            remaining_time = timeout - (time.time() - start_time)
            if remaining_time <= 0:
                logger.warning(f"Drain timeout reached, {len(self._in_flight)} requests still in-flight")
                return False
            
            logger.debug(f"Waiting for {len(self._in_flight)} in-flight requests, {remaining_time:.1f}s remaining")
            await asyncio.sleep(min(0.5, remaining_time))
        
        logger.info(f"All requests drained in {time.time() - start_time:.2f}s")
        return True


class LifecycleManager:
    """
    Manage runtime lifecycle, graceful shutdown, and signal handling.
    
    Responsibilities:
    - Handle SIGTERM/SIGINT signals
    - Track in-flight requests
    - Coordinate graceful shutdown with timeout
    - Support startup rollback on failure
    - Emit lifecycle events
    """
    
    def __init__(
        self,
        shutdown_timeout: float = 30.0,
        enable_signal_handlers: bool = True
    ):
        """
        Initialize lifecycle manager.
        
        Args:
            shutdown_timeout: Maximum time to wait for graceful shutdown (seconds)
            enable_signal_handlers: Whether to register signal handlers
        """
        self._state = LifecycleState.STOPPED
        self._shutdown_timeout = shutdown_timeout
        self._enable_signal_handlers = enable_signal_handlers
        self._request_tracker = RequestTracker()
        self._shutdown_callbacks: list[Callable] = []
        self._state_callbacks: list[Callable] = []
        self._shutdown_event = asyncio.Event()
        self._signal_received: Optional[signal.Signals] = None
        self._startup_services: list[str] = []  # Track services started during initialization
    
    def set_state(self, new_state: LifecycleState) -> None:
        """
        Update lifecycle state and notify callbacks.
        
        Args:
            new_state: New lifecycle state
        """
        old_state = self._state
        if old_state == new_state:
            return
        
        logger.info(f"Lifecycle state transition: {old_state} -> {new_state}")
        self._state = new_state
        
        # Notify state change callbacks
        for callback in self._state_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state callback: {e}", exc_info=True)
    
    def get_state(self) -> LifecycleState:
        """Get current lifecycle state."""
        return self._state
    
    def is_draining(self) -> bool:
        """Check if runtime is in draining state."""
        return self._state == LifecycleState.DRAINING
    
    def register_signal_handlers(self) -> None:
        """
        Register handlers for SIGTERM and SIGINT.
        
        This should be called from the main thread.
        """
        if not self._enable_signal_handlers:
            logger.info("Signal handlers disabled")
            return
        
        try:
            # Get the event loop
            loop = asyncio.get_event_loop()
            
            # Register signal handlers
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: self._handle_signal(s)
                )
            
            logger.info("Registered signal handlers for SIGTERM and SIGINT")
            
        except Exception as e:
            logger.error(f"Failed to register signal handlers: {e}", exc_info=True)
    
    def _handle_signal(self, sig: signal.Signals) -> None:
        """
        Handle shutdown signal.
        
        Args:
            sig: Signal received
        
        Note:
            This is a synchronous function called by asyncio signal handlers.
        """
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown")
        self._signal_received = sig
        self._shutdown_event.set()
    
    def register_shutdown_callback(self, callback: Callable) -> None:
        """
        Register callback to be called during shutdown.
        
        Callbacks should be async functions that accept shutdown_reason as argument.
        
        Args:
            callback: Async callable to invoke during shutdown
        """
        self._shutdown_callbacks.append(callback)
    
    def register_state_callback(self, callback: Callable) -> None:
        """
        Register callback for state changes.
        
        Callbacks should accept (old_state, new_state) as arguments.
        
        Args:
            callback: Callable to invoke on state changes
        """
        self._state_callbacks.append(callback)
    
    async def wait_for_shutdown_signal(self) -> Optional[signal.Signals]:
        """
        Wait for shutdown signal.
        
        Returns:
            Signal that triggered shutdown, or None if no signal
        """
        await self._shutdown_event.wait()
        return self._signal_received
    
    async def graceful_shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.MANUAL
    ) -> bool:
        """
        Perform graceful shutdown.
        
        Steps:
        1. Enter draining state
        2. Stop accepting new requests
        3. Wait for in-flight requests to complete (with timeout)
        4. Call shutdown callbacks
        5. Enter stopped state
        
        Args:
            reason: Reason for shutdown
        
        Returns:
            True if shutdown completed within timeout, False if forced
        """
        logger.info(f"Starting graceful shutdown (reason: {reason})")
        start_time = time.time()
        
        # Set draining state
        self.set_state(LifecycleState.DRAINING)
        await self._request_tracker.start_draining()
        
        # Wait for in-flight requests with timeout
        drain_success = await self._request_tracker.wait_for_drain(self._shutdown_timeout)
        
        # Set stopping state
        self.set_state(LifecycleState.STOPPING)
        
        # Calculate remaining time for shutdown callbacks
        elapsed = time.time() - start_time
        remaining_timeout = max(0, self._shutdown_timeout - elapsed)
        
        # Execute shutdown callbacks
        if self._shutdown_callbacks:
            logger.info(f"Executing {len(self._shutdown_callbacks)} shutdown callback(s)")
            
            for callback in self._shutdown_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await asyncio.wait_for(callback(reason), timeout=remaining_timeout / len(self._shutdown_callbacks))
                    else:
                        callback(reason)
                except asyncio.TimeoutError:
                    logger.warning(f"Shutdown callback {callback.__name__} timed out")
                    drain_success = False
                except Exception as e:
                    logger.error(f"Error in shutdown callback {callback.__name__}: {e}", exc_info=True)
        
        # Final state
        self.set_state(LifecycleState.STOPPED)
        
        total_time = time.time() - start_time
        if drain_success:
            logger.info(f"Graceful shutdown completed in {total_time:.2f}s")
        else:
            logger.warning(f"Forced shutdown after {total_time:.2f}s (timeout: {self._shutdown_timeout}s)")
        
        return drain_success
    
    def track_service_startup(self, service_name: str) -> None:
        """
        Track service started during initialization.
        
        Used for rollback if initialization fails.
        
        Args:
            service_name: Name of service that started
        """
        self._startup_services.append(service_name)
        logger.debug(f"Tracking service startup: {service_name}")
    
    async def rollback_startup(self, stop_service_callback: Callable[[str], Any]) -> None:
        """
        Rollback startup by stopping services in reverse order.
        
        Args:
            stop_service_callback: Async function to stop a service by name
        """
        if not self._startup_services:
            logger.info("No services to rollback")
            return
        
        logger.info(f"Rolling back {len(self._startup_services)} service(s)")
        
        # Stop services in reverse order
        for service_name in reversed(self._startup_services):
            try:
                logger.info(f"Rolling back service: {service_name}")
                if asyncio.iscoroutinefunction(stop_service_callback):
                    await stop_service_callback(service_name)
                else:
                    stop_service_callback(service_name)
            except Exception as e:
                logger.error(f"Error rolling back service {service_name}: {e}", exc_info=True)
        
        self._startup_services.clear()
        logger.info("Startup rollback complete")
    
    def clear_startup_tracking(self) -> None:
        """Clear startup tracking after successful initialization."""
        self._startup_services.clear()
    
    def get_request_tracker(self) -> RequestTracker:
        """Get the request tracker instance."""
        return self._request_tracker
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get lifecycle metrics.
        
        Returns:
            Dictionary with lifecycle metrics
        """
        return {
            "state": self._state.value,
            "in_flight_requests": self._request_tracker.get_in_flight_count(),
            "shutdown_timeout": self._shutdown_timeout,
            "signal_received": self._signal_received.name if self._signal_received else None,
            "startup_services_tracked": len(self._startup_services)
        }
