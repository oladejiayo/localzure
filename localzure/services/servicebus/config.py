"""
Service Bus Configuration Management

Loads configuration from environment variables and YAML files.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

import os
from pathlib import Path
from typing import Optional

import yaml

from .storage import StorageConfig, StorageType


def load_storage_config(config_file: Optional[str] = None) -> StorageConfig:
    """
    Load storage configuration from file or environment variables.
    
    Priority order:
    1. Environment variables (highest priority)
    2. Config file (if specified)
    3. Default values (in-memory storage)
    
    Environment Variables:
    - LOCALZURE_STORAGE_TYPE: "in-memory", "sqlite", "json", or "redis"
    - LOCALZURE_SQLITE_PATH: Path to SQLite database file
    - LOCALZURE_JSON_PATH: Path to JSON storage directory
    - LOCALZURE_SNAPSHOT_INTERVAL: Snapshot interval in seconds
    - LOCALZURE_WAL_ENABLED: "true" or "false"
    - LOCALZURE_AUTO_COMPACT: "true" or "false"
    
    Args:
        config_file: Path to YAML configuration file
    
    Returns:
        StorageConfig object
    
    Example YAML:
        ```yaml
        storage:
          type: sqlite
          sqlite:
            path: ./data/servicebus.db
            wal_enabled: true
          snapshot_interval_seconds: 60
          auto_compact: true
        ```
    """
    config_data = {}
    
    # Load from file if specified
    if config_file and Path(config_file).exists():
        with open(config_file, 'r') as f:
            file_config = yaml.safe_load(f)
            if file_config and "storage" in file_config:
                config_data = file_config["storage"]
    
    # Override with environment variables
    storage_type_str = os.getenv("LOCALZURE_STORAGE_TYPE", config_data.get("type", "in-memory"))
    
    # Map storage type string to enum
    storage_type_map = {
        "in-memory": StorageType.IN_MEMORY,
        "sqlite": StorageType.SQLITE,
        "json": StorageType.JSON,
        "redis": StorageType.REDIS,
    }
    storage_type = storage_type_map.get(storage_type_str, StorageType.IN_MEMORY)
    
    # Build configuration
    config = StorageConfig(
        storage_type=storage_type,
        sqlite_path=os.getenv(
            "LOCALZURE_SQLITE_PATH",
            config_data.get("sqlite", {}).get("path", "./data/servicebus.db")
        ),
        json_path=os.getenv(
            "LOCALZURE_JSON_PATH",
            config_data.get("json", {}).get("path", "./data")
        ),
        redis_host=os.getenv(
            "LOCALZURE_REDIS_HOST",
            config_data.get("redis", {}).get("host", "localhost")
        ),
        redis_port=int(os.getenv(
            "LOCALZURE_REDIS_PORT",
            str(config_data.get("redis", {}).get("port", 6379))
        )),
        redis_db=int(os.getenv(
            "LOCALZURE_REDIS_DB",
            str(config_data.get("redis", {}).get("db", 0))
        )),
        redis_password=os.getenv(
            "LOCALZURE_REDIS_PASSWORD",
            config_data.get("redis", {}).get("password")
        ),
        snapshot_interval_seconds=int(os.getenv(
            "LOCALZURE_SNAPSHOT_INTERVAL",
            str(config_data.get("snapshot_interval_seconds", 60))
        )),
        wal_enabled=os.getenv(
            "LOCALZURE_WAL_ENABLED",
            str(config_data.get("wal_enabled", True))
        ).lower() == "true",
        auto_compact=os.getenv(
            "LOCALZURE_AUTO_COMPACT",
            str(config_data.get("auto_compact", True))
        ).lower() == "true",
        pretty_json=os.getenv(
            "LOCALZURE_PRETTY_JSON",
            str(config_data.get("pretty_json", False))
        ).lower() == "true",
    )
    
    return config


def create_default_config_file(path: str = "./config.yaml"):
    """
    Create a default configuration file with examples.
    
    Args:
        path: Path where to create the config file
    """
    default_config = {
        "storage": {
            "type": "sqlite",
            "sqlite": {
                "path": "./data/servicebus.db",
                "wal_enabled": True
            },
            "json": {
                "path": "./data",
                "pretty": False
            },
            "redis": {
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "password": None
            },
            "snapshot_interval_seconds": 60,
            "auto_compact": True
        }
    }
    
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created default configuration file: {path}")
    print("\nTo use persistence, set environment variable:")
    print("  LOCALZURE_STORAGE_TYPE=sqlite")
    print("\nOr edit config.yaml and specify --config flag when starting LocalZure.")
