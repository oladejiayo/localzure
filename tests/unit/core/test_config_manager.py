"""
Tests for ConfigManager.
"""

import os
import json
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from localzure.core.config_manager import (
    ConfigManager,
    LocalZureConfig,
    LogLevel,
    StateBackendType,
    ServiceConfig,
    GatewayConfig
)


class TestConfigManager:
    """Test suite for ConfigManager."""
    
    def test_load_defaults(self):
        """Test loading default configuration."""
        manager = ConfigManager()
        config = manager.load()
        
        assert config is not None
        assert config.version == "0.1.0"
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.logging.level == LogLevel.INFO
        assert config.state_backend.type == StateBackendType.MEMORY
    
    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_config = {
                "version": "1.0.0",
                "server": {
                    "host": "127.0.0.1",
                    "port": 9000
                },
                "logging": {
                    "level": "DEBUG"
                }
            }
            yaml.dump(yaml_config, f)
            config_file = f.name
        
        try:
            manager = ConfigManager()
            config = manager.load(config_file=config_file)
            
            assert config.version == "1.0.0"
            assert config.server.host == "127.0.0.1"
            assert config.server.port == 9000
            assert config.logging.level == LogLevel.DEBUG
        finally:
            os.unlink(config_file)
    
    def test_load_from_json_file(self):
        """Test loading configuration from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_config = {
                "version": "2.0.0",
                "server": {
                    "host": "localhost",
                    "port": 7000
                }
            }
            json.dump(json_config, f)
            config_file = f.name
        
        try:
            manager = ConfigManager()
            config = manager.load(config_file=config_file)
            
            assert config.version == "2.0.0"
            assert config.server.host == "localhost"
            assert config.server.port == 7000
        finally:
            os.unlink(config_file)
    
    def test_load_from_env_variables(self):
        """Test loading configuration from environment variables."""
        os.environ["LOCALZURE_HOST"] = "192.168.1.1"
        os.environ["LOCALZURE_PORT"] = "5000"
        os.environ["LOCALZURE_LOG_LEVEL"] = "warning"
        os.environ["LOCALZURE_STATE_BACKEND"] = "redis"
        
        try:
            manager = ConfigManager()
            config = manager.load()
            
            assert config.server.host == "192.168.1.1"
            assert config.server.port == 5000
            assert config.logging.level == LogLevel.WARNING
            assert config.state_backend.type == StateBackendType.REDIS
        finally:
            del os.environ["LOCALZURE_HOST"]
            del os.environ["LOCALZURE_PORT"]
            del os.environ["LOCALZURE_LOG_LEVEL"]
            del os.environ["LOCALZURE_STATE_BACKEND"]
    
    def test_cli_overrides(self):
        """Test CLI argument overrides."""
        manager = ConfigManager()
        cli_overrides = {
            "server": {
                "host": "10.0.0.1",
                "port": 3000
            },
            "logging": {
                "level": "ERROR"
            }
        }
        
        config = manager.load(cli_overrides=cli_overrides)
        
        assert config.server.host == "10.0.0.1"
        assert config.server.port == 3000
        assert config.logging.level == LogLevel.ERROR
    
    def test_configuration_precedence(self):
        """Test configuration precedence: CLI > ENV > FILE > DEFAULTS."""
        # Create config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_config = {
                "server": {
                    "host": "file-host",
                    "port": 1111
                }
            }
            yaml.dump(yaml_config, f)
            config_file = f.name
        
        # Set environment variable
        os.environ["LOCALZURE_HOST"] = "env-host"
        
        # Set CLI override
        cli_overrides = {
            "server": {
                "port": 2222
            }
        }
        
        try:
            manager = ConfigManager()
            config = manager.load(
                config_file=config_file,
                cli_overrides=cli_overrides
            )
            
            # CLI port should override file
            assert config.server.port == 2222
            # ENV host should override file
            assert config.server.host == "env-host"
        finally:
            os.unlink(config_file)
            del os.environ["LOCALZURE_HOST"]
    
    def test_invalid_version_format(self):
        """Test that invalid version format raises validation error."""
        manager = ConfigManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.load(cli_overrides={"version": "1.0"})
        
        assert "Version must be in format x.y.z" in str(exc_info.value)
    
    def test_invalid_version_non_numeric(self):
        """Test that non-numeric version components raise validation error."""
        manager = ConfigManager()
        
        with pytest.raises(ValidationError) as exc_info:
            manager.load(cli_overrides={"version": "1.x.0"})
        
        assert "Version components must be numeric" in str(exc_info.value)
    
    def test_file_not_found(self):
        """Test that missing config file raises FileNotFoundError."""
        manager = ConfigManager()
        
        with pytest.raises(FileNotFoundError):
            manager.load(config_file="/nonexistent/config.yaml")
    
    def test_unsupported_file_format(self):
        """Test that unsupported file format raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("invalid config")
            config_file = f.name
        
        try:
            manager = ConfigManager()
            with pytest.raises(ValueError) as exc_info:
                manager.load(config_file=config_file)
            
            assert "Unsupported config file format" in str(exc_info.value)
        finally:
            os.unlink(config_file)
    
    def test_get_config_before_load(self):
        """Test that getting config before loading raises RuntimeError."""
        manager = ConfigManager()
        
        with pytest.raises(RuntimeError) as exc_info:
            manager.get_config()
        
        assert "Configuration not loaded" in str(exc_info.value)
    
    def test_get_config_after_load(self):
        """Test getting config after loading."""
        manager = ConfigManager()
        config1 = manager.load()
        config2 = manager.get_config()
        
        assert config1 is config2
    
    def test_reload_configuration(self):
        """Test reloading configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_config = {"server": {"port": 5555}}
            yaml.dump(yaml_config, f)
            config_file = f.name
        
        try:
            manager = ConfigManager()
            config1 = manager.load(config_file=config_file)
            assert config1.server.port == 5555
            
            # Modify file
            with open(config_file, 'w') as f:
                yaml_config = {"server": {"port": 6666}}
                yaml.dump(yaml_config, f)
            
            # Reload
            config2 = manager.reload()
            assert config2.server.port == 6666
        finally:
            os.unlink(config_file)
    
    def test_service_configuration(self):
        """Test service-specific configuration."""
        manager = ConfigManager()
        config = manager.load(cli_overrides={
            "services": {
                "blob": {
                    "enabled": True,
                    "port": 10000
                },
                "queue": {
                    "enabled": False
                }
            }
        })
        
        assert config.services["blob"].enabled is True
        assert config.services["blob"].port == 10000
        assert config.services["queue"].enabled is False
    
    def test_docker_configuration(self):
        """Test Docker-related configuration."""
        manager = ConfigManager()
        config = manager.load(cli_overrides={
            "docker_enabled": True,
            "services": {
                "blob": {
                    "docker": True,
                    "docker_image": "mcr.microsoft.com/azure-storage/azurite"
                }
            }
        })
        
        assert config.docker_enabled is True
        assert config.services["blob"].docker is True
        assert config.services["blob"].docker_image == "mcr.microsoft.com/azure-storage/azurite"


class TestLocalZureConfig:
    """Test suite for LocalZureConfig model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LocalZureConfig()
        
        assert config.version == "0.1.0"
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.logging.level == LogLevel.INFO
        assert config.state_backend.type == StateBackendType.MEMORY
        assert config.docker_enabled is False
    
    def test_service_defaults(self):
        """Test default service configurations."""
        config = LocalZureConfig()
        
        assert "blob" in config.services
        assert "queue" in config.services
        assert "table" in config.services
        assert "servicebus" in config.services
        assert "keyvault" in config.services
        assert "cosmos" in config.services
        
        # All services should be disabled by default
        for service in config.services.values():
            assert service.enabled is False


class TestGatewayConfig:
    """Test suite for GatewayConfig model."""
    
    def test_default_gateway_config(self):
        """Test default gateway configuration values."""
        config = GatewayConfig()
        
        assert config.enabled is True
        assert config.custom_mappings == {}
        assert config.preserve_host_header is True
    
    def test_custom_mappings(self):
        """Test custom hostname mappings."""
        config = GatewayConfig(
            custom_mappings={
                "custom.domain.com": "http://localhost:9000",
                "another.example.com": "http://localhost:9001"
            }
        )
        
        assert len(config.custom_mappings) == 2
        assert config.custom_mappings["custom.domain.com"] == "http://localhost:9000"
        assert config.custom_mappings["another.example.com"] == "http://localhost:9001"
    
    def test_gateway_disabled(self):
        """Test disabling gateway."""
        config = GatewayConfig(enabled=False)
        
        assert config.enabled is False
    
    def test_gateway_in_localzure_config(self):
        """Test gateway config as part of LocalZure config."""
        config = LocalZureConfig()
        
        assert config.gateway is not None
        assert config.gateway.enabled is True
        assert isinstance(config.gateway, GatewayConfig)
    
    def test_load_gateway_config_from_yaml(self):
        """Test loading gateway configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_config = {
                "gateway": {
                    "enabled": True,
                    "preserve_host_header": False,
                    "custom_mappings": {
                        "custom.blob.example.com": "http://localhost:11000"
                    }
                }
            }
            yaml.dump(yaml_config, f)
            config_file = f.name
        
        try:
            manager = ConfigManager()
            config = manager.load(config_file=config_file)
            
            assert config.gateway.enabled is True
            assert config.gateway.preserve_host_header is False
            assert "custom.blob.example.com" in config.gateway.custom_mappings
            assert config.gateway.custom_mappings["custom.blob.example.com"] == "http://localhost:11000"
        finally:
            Path(config_file).unlink()

