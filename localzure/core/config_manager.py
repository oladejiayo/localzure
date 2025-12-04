"""
Configuration management for LocalZure.

Handles loading, validation, and access to configuration settings.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
from enum import Enum

import yaml
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Valid log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StateBackendType(str, Enum):
    """Supported state backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    SQLITE = "sqlite"
    FILE = "file"


class ServiceConfig(BaseModel):
    """Configuration for individual services."""
    enabled: bool = True
    port: Optional[int] = None
    docker: bool = False
    docker_image: Optional[str] = None


class StateBackendConfig(BaseModel):
    """State backend configuration."""
    type: StateBackendType = StateBackendType.MEMORY
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    key_prefix: str = "localzure:"
    sqlite_path: Optional[str] = None
    file_path: Optional[str] = None


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "json"
    file: Optional[str] = None
    rotation_size: str = "10MB"
    rotation_count: int = 5
    module_levels: Optional[Dict[str, str]] = Field(
        default=None,
        description="Per-module log levels, e.g., {'localzure.core.runtime': 'DEBUG'}"
    )


class GatewayConfig(BaseModel):
    """API Gateway configuration."""
    enabled: bool = True
    custom_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom hostname to local endpoint mappings"
    )
    preserve_host_header: bool = Field(
        default=True,
        description="Preserve original Azure hostname in X-Original-Host header"
    )


class ServerConfig(BaseModel):
    """HTTP server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    shutdown_timeout: float = Field(
        default=30.0,
        ge=0.0,
        description="Graceful shutdown timeout in seconds"
    )


class LocalZureConfig(BaseModel):
    """Main LocalZure configuration schema."""
    
    version: str = Field(default="0.1.0", description="Configuration version")
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    state_backend: StateBackendConfig = Field(default_factory=StateBackendConfig)
    
    services: Dict[str, ServiceConfig] = Field(
        default_factory=lambda: {
            "blob": ServiceConfig(enabled=False, port=10000),
            "queue": ServiceConfig(enabled=False, port=10001),
            "table": ServiceConfig(enabled=False, port=10002),
            "servicebus": ServiceConfig(enabled=False, port=5672),
            "keyvault": ServiceConfig(enabled=False, port=8200),
            "cosmos": ServiceConfig(enabled=False, port=8081),
        }
    )
    
    docker_enabled: bool = False
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be in format x.y.z")
        for part in parts:
            if not part.isdigit():
                raise ValueError("Version components must be numeric")
        return v
    
    model_config = ConfigDict(use_enum_values=True)


class ConfigManager:
    """
    Manages LocalZure configuration loading and validation.
    
    Configuration precedence (highest to lowest):
    1. CLI arguments
    2. Environment variables (LOCALZURE_*)
    3. Configuration file (YAML/JSON)
    4. Defaults
    """
    
    def __init__(self):
        self._config: Optional[LocalZureConfig] = None
        self._config_file: Optional[Path] = None
    
    def load(
        self,
        config_file: Optional[str] = None,
        cli_overrides: Optional[Dict[str, Any]] = None
    ) -> LocalZureConfig:
        """
        Load and validate configuration from multiple sources.
        
        Args:
            config_file: Path to configuration file (YAML or JSON)
            cli_overrides: Dictionary of CLI argument overrides
        
        Returns:
            Validated LocalZureConfig instance
        
        Raises:
            ValidationError: If configuration is invalid
            FileNotFoundError: If specified config file doesn't exist
        """
        logger.info("Loading LocalZure configuration")
        
        # Start with defaults
        config_dict: Dict[str, Any] = {}
        
        # Load from file if specified
        if config_file:
            config_dict = self._load_from_file(config_file)
            self._config_file = Path(config_file)
            logger.info(f"Loaded configuration from file: {config_file}")
        
        # Apply environment variables
        env_config = self._load_from_env()
        config_dict = self._merge_configs(config_dict, env_config)
        if env_config:
            logger.info(f"Applied {len(env_config)} environment variable overrides")
        
        # Apply CLI overrides
        if cli_overrides:
            config_dict = self._merge_configs(config_dict, cli_overrides)
            logger.info(f"Applied {len(cli_overrides)} CLI argument overrides")
        
        # Validate and create config object
        try:
            self._config = LocalZureConfig(**config_dict)
            logger.info("Configuration validated successfully")
            self._log_configuration()
            return self._config
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
    
    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from YAML or JSON file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f) or {}
            elif path.suffix == '.json':
                return json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {path.suffix}")
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config: Dict[str, Any] = {}
        
        # Server configuration
        if host := os.getenv("LOCALZURE_HOST"):
            config.setdefault("server", {})["host"] = host
        if port := os.getenv("LOCALZURE_PORT"):
            config.setdefault("server", {})["port"] = int(port)
        
        # Logging configuration
        if log_level := os.getenv("LOCALZURE_LOG_LEVEL"):
            config.setdefault("logging", {})["level"] = log_level.upper()
        if log_file := os.getenv("LOCALZURE_LOG_FILE"):
            config.setdefault("logging", {})["file"] = log_file
        
        # State backend configuration
        if backend_type := os.getenv("LOCALZURE_STATE_BACKEND"):
            config.setdefault("state_backend", {})["type"] = backend_type
        if redis_host := os.getenv("LOCALZURE_REDIS_HOST"):
            config.setdefault("state_backend", {})["host"] = redis_host
        if redis_port := os.getenv("LOCALZURE_REDIS_PORT"):
            config.setdefault("state_backend", {})["port"] = int(redis_port)
        
        # Docker configuration
        if docker_enabled := os.getenv("LOCALZURE_DOCKER_ENABLED"):
            config["docker_enabled"] = docker_enabled.lower() in ['true', '1', 'yes']
        
        return config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _log_configuration(self) -> None:
        """Log the loaded configuration (with sensitive data redacted)."""
        if not self._config:
            return
        
        config_dict = self._config.model_dump()
        
        # Redact sensitive fields
        if "state_backend" in config_dict and "password" in config_dict["state_backend"]:
            if config_dict["state_backend"]["password"]:
                config_dict["state_backend"]["password"] = "***REDACTED***"
        
        logger.info(f"Active configuration: {json.dumps(config_dict, indent=2)}")
    
    def get_config(self) -> LocalZureConfig:
        """
        Get the loaded configuration.
        
        Returns:
            LocalZureConfig instance
        
        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config
    
    def reload(self) -> LocalZureConfig:
        """
        Reload configuration from the same sources.
        
        Returns:
            Reloaded LocalZureConfig instance
        """
        config_file = str(self._config_file) if self._config_file else None
        return self.load(config_file=config_file)
