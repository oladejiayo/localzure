"""
LocalZure Core Runtime.

Main runtime class that orchestrates system initialization, lifecycle, and health checks.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from .config_manager import ConfigManager, LocalZureConfig
from .logging_config import setup_logging, get_logger
from .service_manager import ServiceManager

logger = get_logger(__name__)


class LocalZureRuntime:
    """
    Core runtime for LocalZure.
    
    Manages system initialization, configuration, lifecycle, and health monitoring.
    """
    
    def __init__(self):
        self._config_manager = ConfigManager()
        self._service_manager: Optional[ServiceManager] = None
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
            
            # Step 3: Initialize Service Manager
            service_config = self._config.services if self._config.services else {}
            docker_enabled = self._config.docker_enabled if hasattr(self._config, 'docker_enabled') else False
            self._service_manager = ServiceManager(config=service_config, docker_enabled=docker_enabled)
            self._service_manager.discover_services()
            await self._service_manager.initialize()
            logger.info(f"Service manager initialized with {self._service_manager.service_count} service(s)")
            
            # Step 4: Initialize FastAPI application
            self._app = self._create_fastapi_app()
            
            # Step 5: Register health check endpoint
            self._register_health_endpoint()
            
            # Mark initialization as complete
            self._initialization_complete = True
            self._start_time = time.time()
            
            logger.info("LocalZure runtime initialization complete")
            
        except Exception as e:
            logger.error(f"Runtime initialization failed: {e}", exc_info=True)
            # Ensure we can retry initialization
            self._initialization_complete = False
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
            # Future: Start service manager and services here
            
            self._is_running = True
            logger.info("LocalZure runtime started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start runtime: {e}", exc_info=True)
            self._is_running = False
            raise
    
    async def stop(self) -> None:
        """
        Stop the LocalZure runtime gracefully.
        """
        if not self._is_running:
            logger.warning("Runtime not running")
            return
        
        logger.info("Stopping LocalZure runtime")
        
        try:
            # Stop and cleanup service manager
            if self._service_manager:
                await self._service_manager.shutdown()
            
            self._is_running = False
            logger.info("LocalZure runtime stopped")
            
        except Exception as e:
            logger.error(f"Error during runtime shutdown: {e}", exc_info=True)
            raise
    
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
        
        logger.info("Runtime reset complete")
    
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
