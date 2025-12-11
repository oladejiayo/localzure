"""
Tests for Storage Backends

Tests the persistence layer implementation for Service Bus.

Author: Ayodele Oladeji
Date: December 11, 2025
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from localzure.services.servicebus.storage import (
    StorageConfig,
    StorageType,
    InMemoryStorage,
    SQLiteStorage,
    JSONStorage,
    create_storage_backend,
)


@pytest.fixture
async def temp_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def inmemory_storage():
    """Create in-memory storage backend."""
    config = StorageConfig(storage_type=StorageType.IN_MEMORY)
    storage = InMemoryStorage(config)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
async def sqlite_storage(temp_dir):
    """Create SQLite storage backend."""
    config = StorageConfig(
        storage_type=StorageType.SQLITE,
        sqlite_path=str(temp_dir / "test.db"),
        wal_enabled=True
    )
    storage = SQLiteStorage(config)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
async def json_storage(temp_dir):
    """Create JSON storage backend."""
    config = StorageConfig(
        storage_type=StorageType.JSON,
        json_path=str(temp_dir),
        pretty_json=True
    )
    storage = JSONStorage(config)
    await storage.initialize()
    yield storage
    await storage.close()


class TestInMemoryStorage:
    """Test InMemoryStorage backend."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, inmemory_storage):
        """Test storage initializes correctly."""
        stats = await inmemory_storage.get_storage_stats()
        assert stats["storage_type"] == "in-memory"
        assert stats["persistent"] is False
    
    @pytest.mark.asyncio
    async def test_save_and_load_entity(self, inmemory_storage):
        """Test saving and loading entities (no-op in memory)."""
        # Save entity (no-op)
        await inmemory_storage.save_entity("queue", "test-queue", {"prop": "value"})
        
        # Load entities (returns empty)
        entities = await inmemory_storage.load_entities("queue")
        assert entities == {}


class TestSQLiteStorage:
    """Test SQLiteStorage backend."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, sqlite_storage, temp_dir):
        """Test SQLite storage initializes correctly."""
        db_path = temp_dir / "test.db"
        assert db_path.exists()
        
        stats = await sqlite_storage.get_storage_stats()
        assert stats["storage_type"] == "sqlite"
        assert stats["persistent"] is True
        assert stats["wal_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_save_and_load_entity(self, sqlite_storage):
        """Test saving and loading entities."""
        # Save entity
        entity_data = {
            "name": "test-queue",
            "max_size": 1024,
            "lock_duration": 60
        }
        await sqlite_storage.save_entity("queue", "test-queue", entity_data)
        
        # Load entities
        entities = await sqlite_storage.load_entities("queue")
        assert "test-queue" in entities
        assert entities["test-queue"]["name"] == "test-queue"
        assert entities["test-queue"]["max_size"] == 1024
    
    @pytest.mark.asyncio
    async def test_save_and_load_message(self, sqlite_storage):
        """Test saving and loading messages."""
        # Save message
        message_data = {
            "message_id": "msg-1",
            "body": "Hello World",
            "user_properties": {"key": "value"}
        }
        await sqlite_storage.save_message(
            "test-queue",
            "msg-1",
            message_data,
            state="active"
        )
        
        # Load messages
        messages = await sqlite_storage.load_messages("test-queue", state="active")
        assert len(messages) == 1
        assert messages[0]["message_id"] == "msg-1"
        assert messages[0]["body"] == "Hello World"
    
    @pytest.mark.asyncio
    async def test_delete_entity(self, sqlite_storage):
        """Test deleting entities."""
        # Save entity
        await sqlite_storage.save_entity("queue", "test-queue", {"name": "test-queue"})
        
        # Verify it exists
        entities = await sqlite_storage.load_entities("queue")
        assert "test-queue" in entities
        
        # Delete entity
        await sqlite_storage.delete_entity("queue", "test-queue")
        
        # Verify it's gone
        entities = await sqlite_storage.load_entities("queue")
        assert "test-queue" not in entities
    
    @pytest.mark.asyncio
    async def test_state_operations(self, sqlite_storage):
        """Test saving and loading state."""
        # Save state
        await sqlite_storage.save_state("counter", 42)
        await sqlite_storage.save_state("config", {"setting": "value"})
        
        # Load state
        counter = await sqlite_storage.load_state("counter")
        assert counter == 42
        
        config = await sqlite_storage.load_state("config")
        assert config["setting"] == "value"
        
        # Non-existent key
        missing = await sqlite_storage.load_state("nonexistent")
        assert missing is None
    
    @pytest.mark.asyncio
    async def test_export_import(self, sqlite_storage, temp_dir):
        """Test export and import functionality."""
        # Save some data
        await sqlite_storage.save_entity("queue", "q1", {"name": "q1"})
        await sqlite_storage.save_entity("queue", "q2", {"name": "q2"})
        await sqlite_storage.save_message("q1", "msg-1", {"body": "test"})
        await sqlite_storage.save_state("key", "value")
        
        # Export
        export_path = temp_dir / "export.json"
        await sqlite_storage.export_data(str(export_path))
        assert export_path.exists()
        
        # Verify export file structure
        with open(export_path) as f:
            export_data = json.load(f)
            assert "entities" in export_data
            assert "messages" in export_data
            assert "state" in export_data
        
        # Clear storage
        await sqlite_storage.purge()
        entities = await sqlite_storage.load_entities("queue")
        assert len(entities) == 0
        
        # Import
        await sqlite_storage.import_data(str(export_path))
        
        # Verify data restored
        entities = await sqlite_storage.load_entities("queue")
        assert len(entities) == 2
        assert "q1" in entities
        assert "q2" in entities
        
        messages = await sqlite_storage.load_messages("q1")
        assert len(messages) == 1
        
        state = await sqlite_storage.load_state("key")
        assert state == "value"


class TestJSONStorage:
    """Test JSONStorage backend."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, json_storage, temp_dir):
        """Test JSON storage initializes correctly."""
        assert (temp_dir / "entities").exists()
        assert (temp_dir / "messages").exists()
        assert (temp_dir / "state.json").exists()
        
        stats = await json_storage.get_storage_stats()
        assert stats["storage_type"] == "json"
        assert stats["persistent"] is True
    
    @pytest.mark.asyncio
    async def test_save_and_load_entity(self, json_storage, temp_dir):
        """Test saving and loading entities."""
        # Save entity
        entity_data = {"name": "test-queue", "max_size": 1024}
        await json_storage.save_entity("queue", "test-queue", entity_data)
        
        # Verify file created
        queue_file = temp_dir / "entities" / "queue.json"
        assert queue_file.exists()
        
        # Load entities
        entities = await json_storage.load_entities("queue")
        assert "test-queue" in entities
        assert entities["test-queue"]["name"] == "test-queue"
    
    @pytest.mark.asyncio
    async def test_human_readable_format(self, json_storage, temp_dir):
        """Test that JSON files are human-readable."""
        # Save entity
        await json_storage.save_entity("queue", "test-queue", {"name": "test-queue"})
        
        # Read raw file
        queue_file = temp_dir / "entities" / "queue.json"
        with open(queue_file) as f:
            content = f.read()
            # Should be pretty-printed
            assert "\n" in content
            assert "  " in content  # Indentation


class TestStorageFactory:
    """Test storage backend factory."""
    
    def test_create_inmemory_backend(self):
        """Test creating in-memory backend."""
        config = StorageConfig(storage_type=StorageType.IN_MEMORY)
        storage = create_storage_backend(config)
        assert isinstance(storage, InMemoryStorage)
    
    def test_create_sqlite_backend(self):
        """Test creating SQLite backend."""
        config = StorageConfig(storage_type=StorageType.SQLITE)
        storage = create_storage_backend(config)
        assert isinstance(storage, SQLiteStorage)
    
    def test_create_json_backend(self):
        """Test creating JSON backend."""
        config = StorageConfig(storage_type=StorageType.JSON)
        storage = create_storage_backend(config)
        assert isinstance(storage, JSONStorage)
    
    def test_unsupported_backend(self):
        """Test creating unsupported backend raises error."""
        config = StorageConfig(storage_type=StorageType.REDIS)
        with pytest.raises(Exception) as exc_info:
            create_storage_backend(config)
        assert "not yet implemented" in str(exc_info.value).lower()
