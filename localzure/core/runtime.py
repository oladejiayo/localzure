"""
LocalZure Core Runtime.

Main runtime class that orchestrates system initialization, lifecycle, and health checks.
"""

import asyncio
import logging
import signal
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from .config_manager import ConfigManager, LocalZureConfig
from .logging_config import setup_logging, get_logger
from .service_manager import ServiceManager
from .lifecycle import LifecycleManager, LifecycleState, ShutdownReason

logger = get_logger(__name__)


class LocalZureRuntime:
    """
    Core runtime for LocalZure.
    
    Manages system initialization, configuration, lifecycle, and health monitoring.
    """
    
    def __init__(self):
        self._config_manager = ConfigManager()
        self._service_manager: Optional[ServiceManager] = None
        self._lifecycle_manager: Optional[LifecycleManager] = None
        self._config: Optional[LocalZureConfig] = None
        self._app: Optional[FastAPI] = None
        self._start_time: Optional[float] = None
        self._is_running = False
        self._initialization_complete = False
    
    async def initialize(
        self,
        config_file: Optional[str] = None,
        cli_overrides: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the LocalZure runtime.
        
        This method is idempotent and can be safely called multiple times.
        
        Args:
            config_file: Path to configuration file
            cli_overrides: CLI argument overrides
        
        Raises:
            ValidationError: If configuration is invalid
            RuntimeError: If initialization fails
        """
        if self._initialization_complete:
            logger.info("Runtime already initialized, skipping")
            return
        
        logger.info("Initializing LocalZure runtime")
        
        try:
            # Step 1: Load and validate configuration
            self._config = self._config_manager.load(
                config_file=config_file,
                cli_overrides=cli_overrides
            )
            
            # Step 2: Initialize logging infrastructure
            setup_logging(
                level=self._config.logging.level,
                format_type=self._config.logging.format,
                log_file=self._config.logging.file,
                rotation_size=self._config.logging.rotation_size,
                rotation_count=self._config.logging.rotation_count,
                module_levels=self._config.logging.module_levels
            )
            
            logger.info(f"LocalZure v{self._config.version} initializing")
            
            # Step 3: Initialize Lifecycle Manager
            shutdown_timeout = self._config.server.shutdown_timeout
            self._lifecycle_manager = LifecycleManager(
                shutdown_timeout=shutdown_timeout,
                enable_signal_handlers=True
            )
            self._lifecycle_manager.set_state(LifecycleState.INITIALIZING)
            
            # Register signal handlers (must be in main thread)
            try:
                self._lifecycle_manager.register_signal_handlers()
            except Exception as e:
                logger.warning(f"Failed to register signal handlers: {e}")
            
            # Register shutdown callback
            self._lifecycle_manager.register_shutdown_callback(self._shutdown_callback)
            
            logger.info(f"Lifecycle manager initialized with {shutdown_timeout}s shutdown timeout")
            
            # Step 4: Initialize Service Manager
            service_config = self._config.services if self._config.services else {}
            docker_enabled = self._config.docker_enabled if hasattr(self._config, 'docker_enabled') else False
            self._service_manager = ServiceManager(config=service_config, docker_enabled=docker_enabled)
            self._service_manager.discover_services()
            
            # Attempt to initialize services with rollback on failure
            try:
                await self._service_manager.initialize()
                logger.info(f"Service manager initialized with {self._service_manager.service_count} service(s)")
            except Exception as init_error:
                logger.error(f"Service initialization failed: {init_error}", exc_info=True)
                # Rollback: stop any services that were started
                await self._lifecycle_manager.rollback_startup(self._service_manager.stop_service)
                raise RuntimeError(f"Failed to initialize services: {init_error}") from init_error
            
            # Step 5: Initialize FastAPI application
            self._app = self._create_fastapi_app()
            
            # Step 6: Register health check endpoint
            self._register_health_endpoint()
            
            # Mark initialization as complete
            self._initialization_complete = True
            self._start_time = time.time()
            self._lifecycle_manager.set_state(LifecycleState.STOPPED)
            self._lifecycle_manager.clear_startup_tracking()
            
            logger.info("LocalZure runtime initialization complete")
            
        except Exception as e:
            logger.error(f"Runtime initialization failed: {e}", exc_info=True)
            # Ensure we can retry initialization
            self._initialization_complete = False
            if self._lifecycle_manager:
                self._lifecycle_manager.set_state(LifecycleState.FAILED)
            raise RuntimeError(f"Failed to initialize LocalZure: {e}") from e
    
    def _create_fastapi_app(self) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(
            title="LocalZure",
            description="Local Azure Cloud Platform Emulator",
            version=self._config.version if self._config else "0.1.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        logger.debug("FastAPI application created")
        return app
    
    def _register_health_endpoint(self) -> None:
        """Register health check endpoint."""
        if not self._app:
            raise RuntimeError("FastAPI app not initialized")
        
        @self._app.get("/health", status_code=status.HTTP_200_OK)
        async def health_check() -> JSONResponse:
            """
            Health check endpoint.
            
            Returns:
                JSON response with system status
            """
            health_status = self.get_health_status()
            
            # Determine HTTP status code based on health
            if health_status["status"] == "healthy":
                status_code = status.HTTP_200_OK
            elif health_status["status"] == "degraded":
                status_code = status.HTTP_200_OK  # Still accept traffic
            elif health_status["status"] == "draining":
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE  # Rejecting new traffic
            else:  # unhealthy
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            return JSONResponse(
                content=health_status,
                status_code=status_code
            )
        
        logger.debug("Health check endpoint registered at /health")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status.
        
        Returns:
            Dictionary containing health status information
        """
        if not self._config:
            return {
                "status": "unhealthy",
                "version": "unknown",
                "services": {},
                "uptime": 0,
                "message": "Runtime not initialized"
            }
        
        # Calculate uptime
        uptime = int(time.time() - self._start_time) if self._start_time else 0
        
        # Get service statuses from service manager
        services_status = {}
        if self._service_manager:
            services_status = self._service_manager.get_all_status()
        else:
            # Fallback to config if service manager not initialized
            for service_name, service_config in self._config.services.items():
                if service_config.enabled:
                    services_status[service_name] = {
                        "status": "unknown",
                        "enabled": True
                    }
        
        # Determine overall status
        if not self._initialization_complete:
            overall_status = "unhealthy"
        elif self._lifecycle_manager and self._lifecycle_manager.is_draining():
            overall_status = "draining"
        elif not self._is_running:
            overall_status = "degraded"
        else:
            # Check if any services are failed
            failed_services = [s for s in services_status.values() if s.get("state") == "failed"]
            if failed_services:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
        
        return {
            "status": overall_status,
            "version": self._config.version,
            "services": services_status,
            "uptime": uptime,
            "in_flight_requests": self._lifecycle_manager.get_request_tracker().get_in_flight_count() if self._lifecycle_manager else 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def start(self) -> None:
        """
        Start the LocalZure runtime.
        
        Raises:
            RuntimeError: If runtime is not initialized
        """
        if not self._initialization_complete:
            raise RuntimeError("Runtime not initialized. Call initialize() first.")
        
        if self._is_running:
            logger.warning("Runtime already running")
            return
        
        logger.info("Starting LocalZure runtime")
        
        try:
            # Set state to starting
            if self._lifecycle_manager:
                self._lifecycle_manager.set_state(LifecycleState.STARTING)
            
            # Future: Start service manager and services here
            
            self._is_running = True
            
            # Set state to running
            if self._lifecycle_manager:
                self._lifecycle_manager.set_state(LifecycleState.RUNNING)
            
            logger.info("LocalZure runtime started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start runtime: {e}", exc_info=True)
            self._is_running = False
            if self._lifecycle_manager:
                self._lifecycle_manager.set_state(LifecycleState.FAILED)
            raise
    
    async def stop(self) -> None:
        """
        Stop the LocalZure runtime gracefully.
        
        Uses lifecycle manager for graceful shutdown with timeout.
        """
        if not self._is_running:
            logger.warning("Runtime not running")
            return
        
        logger.info("Stopping LocalZure runtime")
        
        try:
            # Use lifecycle manager for graceful shutdown
            if self._lifecycle_manager:
                await self._lifecycle_manager.graceful_shutdown(reason=ShutdownReason.MANUAL)
            else:
                # Fallback if lifecycle manager not available
                if self._service_manager:
                    await self._service_manager.shutdown()
            
            self._is_running = False
            logger.info("LocalZure runtime stopped")
            
        except Exception as e:
            logger.error(f"Error during runtime shutdown: {e}", exc_info=True)
            raise
    
    async def _shutdown_callback(self, reason: ShutdownReason) -> None:
        """
        Callback invoked by lifecycle manager during shutdown.
        
        Args:
            reason: Reason for shutdown
        """
        logger.info(f"Executing shutdown callback (reason: {reason})")
        
        # Stop and cleanup service manager
        if self._service_manager:
            await self._service_manager.shutdown()
        
        logger.info("Shutdown callback complete")
    
    async def reset(self) -> None:
        """
        Reset the runtime state.
        
        This stops the runtime, clears state, and prepares for restart.
        """
        logger.info("Resetting LocalZure runtime")
        
        if self._is_running:
            await self.stop()
        
        # Reset state
        self._initialization_complete = False
        self._start_time = None
        
        if self._lifecycle_manager:
            self._lifecycle_manager.set_state(LifecycleState.STOPPED)
        
        logger.info("Runtime reset complete")
    
    async def wait_for_shutdown_signal(self) -> Optional[signal.Signals]:
        """
        Wait for shutdown signal (SIGTERM/SIGINT).
        
        Returns:
            Signal that was received, or None
        """
        if not self._lifecycle_manager:
            raise RuntimeError("Lifecycle manager not initialized")
        
        return await self._lifecycle_manager.wait_for_shutdown_signal()
    
    def get_config(self) -> LocalZureConfig:
        """
        Get the current configuration.
        
        Returns:
            LocalZureConfig instance
        
        Raises:
            RuntimeError: If configuration not loaded
        """
        return self._config_manager.get_config()
    
    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.
        
        Returns:
            FastAPI app instance
        
        Raises:
            RuntimeError: If app not initialized
        """
        if not self._app:
            raise RuntimeError("FastAPI app not initialized")
        return self._app
    
    @property
    def is_running(self) -> bool:
        """Check if runtime is currently running."""
        return self._is_running
    
    @property
    def is_initialized(self) -> bool:
        """Check if runtime is initialized."""
        return self._initialization_complete
