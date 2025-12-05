"""
Unit tests for Table Storage models.

Tests Table, Entity, and request models with validation.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from localzure.services.table.models import (
    Table,
    TableNameValidator,
    Entity,
    InsertEntityRequest,
    UpdateEntityRequest,
    MergeEntityRequest,
)


class TestTableNameValidator:
    """Tests for table name validation."""
    
    def test_valid_table_name(self):
        """Test valid table names."""
        valid_names = ["mytable", "Table123", "abc", "MyTable2024"]
        for name in valid_names:
            is_valid, error = TableNameValidator.validate(name)
            assert is_valid is True
            assert error is None
    
    def test_table_name_too_short(self):
        """Test table name too short."""
        is_valid, error = TableNameValidator.validate("ab")
        assert is_valid is False
        assert "between 3 and 63 characters" in error
    
    def test_table_name_too_long(self):
        """Test table name too long."""
        is_valid, error = TableNameValidator.validate("a" * 64)
        assert is_valid is False
        assert "between 3 and 63 characters" in error
    
    def test_table_name_starts_with_number(self):
        """Test table name starting with number."""
        is_valid, error = TableNameValidator.validate("123table")
        assert is_valid is False
        assert "must start with a letter" in error
    
    def test_table_name_with_hyphens(self):
        """Test table name with hyphens."""
        is_valid, error = TableNameValidator.validate("my-table")
        assert is_valid is False
        assert "alphanumeric" in error
    
    def test_table_name_with_special_chars(self):
        """Test table name with special characters."""
        is_valid, error = TableNameValidator.validate("my_table")
        assert is_valid is False
        assert "alphanumeric" in error
    
    def test_empty_table_name(self):
        """Test empty table name."""
        is_valid, error = TableNameValidator.validate("")
        assert is_valid is False
        assert "cannot be empty" in error


class TestTable:
    """Tests for Table model."""
    
    def test_create_valid_table(self):
        """Test creating a valid table."""
        table = Table(table_name="MyTable")
        assert table.table_name == "MyTable"
    
    def test_create_table_with_numbers(self):
        """Test creating table with numbers."""
        table = Table(table_name="Table123")
        assert table.table_name == "Table123"
    
    def test_create_table_invalid_name(self):
        """Test creating table with invalid name."""
        with pytest.raises(ValidationError) as exc_info:
            Table(table_name="my-table")
        assert "alphanumeric" in str(exc_info.value)
    
    def test_create_table_too_short(self):
        """Test creating table with name too short."""
        with pytest.raises(ValidationError):
            Table(table_name="ab")
    
    def test_create_table_starts_with_number(self):
        """Test creating table with name starting with number."""
        with pytest.raises(ValidationError):
            Table(table_name="123table")


class TestEntity:
    """Tests for Entity model."""
    
    def test_create_basic_entity(self):
        """Test creating a basic entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        assert entity.PartitionKey == "pk1"
        assert entity.RowKey == "rk1"
        assert isinstance(entity.Timestamp, datetime)
    
    def test_create_entity_with_custom_properties(self):
        """Test creating entity with custom properties."""
        entity = Entity(
            PartitionKey="pk1",
            RowKey="rk1",
            Name="John Doe",
            Age=30,
            IsActive=True
        )
        assert entity.PartitionKey == "pk1"
        assert entity.RowKey == "rk1"
        
        custom_props = entity.get_custom_properties()
        assert custom_props["Name"] == "John Doe"
        assert custom_props["Age"] == 30
        assert custom_props["IsActive"] is True
    
    def test_empty_partition_key(self):
        """Test entity with empty partition key."""
        with pytest.raises(ValidationError) as exc_info:
            Entity(PartitionKey="", RowKey="rk1")
        assert "cannot be empty" in str(exc_info.value)
    
    def test_empty_row_key(self):
        """Test entity with empty row key."""
        with pytest.raises(ValidationError) as exc_info:
            Entity(PartitionKey="pk1", RowKey="")
        assert "cannot be empty" in str(exc_info.value)
    
    def test_entity_to_dict(self):
        """Test entity to dictionary conversion."""
        entity = Entity(
            PartitionKey="pk1",
            RowKey="rk1",
            Name="Test"
        )
        entity.etag = 'W/"datetime\'2025-12-04T10%3A30%3A00.123456Z\'"'
        
        entity_dict = entity.to_dict()
        assert entity_dict["PartitionKey"] == "pk1"
        assert entity_dict["RowKey"] == "rk1"
        assert "Timestamp" in entity_dict
        assert entity_dict["odata.etag"] == 'W/"datetime\'2025-12-04T10%3A30%3A00.123456Z\'"'
        assert entity_dict["Name"] == "Test"
    
    def test_entity_from_dict(self):
        """Test entity from dictionary."""
        data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Timestamp": "2025-12-04T10:30:00.123456Z",
            "odata.etag": 'W/"datetime\'2025-12-04T10%3A30%3A00.123456Z\'"',
            "Name": "Test",
            "Age": 25
        }
        
        entity = Entity.from_dict(data)
        assert entity.PartitionKey == "pk1"
        assert entity.RowKey == "rk1"
        assert entity.etag == 'W/"datetime\'2025-12-04T10%3A30%3A00.123456Z\'"'
        
        custom_props = entity.get_custom_properties()
        assert custom_props["Name"] == "Test"
        assert custom_props["Age"] == 25
    
    def test_generate_etag(self):
        """Test ETag generation."""
        timestamp = datetime(2025, 12, 4, 10, 30, 0, 123456, tzinfo=timezone.utc)
        etag = Entity.generate_etag(timestamp)
        
        assert etag.startswith('W/"datetime\'')
        assert etag.endswith('"')
        assert "2025-12-04T10%3A30%3A00.123456Z" in etag
    
    def test_get_custom_properties(self):
        """Test getting custom properties."""
        entity = Entity(
            PartitionKey="pk1",
            RowKey="rk1",
            Property1="value1",
            Property2=42
        )
        
        custom_props = entity.get_custom_properties()
        assert len(custom_props) == 2
        assert custom_props["Property1"] == "value1"
        assert custom_props["Property2"] == 42
        assert "PartitionKey" not in custom_props
        assert "RowKey" not in custom_props


class TestInsertEntityRequest:
    """Tests for InsertEntityRequest model."""
    
    def test_create_insert_request(self):
        """Test creating insert request."""
        request = InsertEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            Name="Test"
        )
        assert request.PartitionKey == "pk1"
        assert request.RowKey == "rk1"
    
    def test_insert_request_to_entity(self):
        """Test converting insert request to entity."""
        request = InsertEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            Property1="value1"
        )
        
        entity = request.to_entity()
        assert entity.PartitionKey == "pk1"
        assert entity.RowKey == "rk1"
        assert entity.get_custom_properties()["Property1"] == "value1"


class TestUpdateEntityRequest:
    """Tests for UpdateEntityRequest model."""
    
    def test_create_update_request(self):
        """Test creating update request."""
        request = UpdateEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            NewProperty="newvalue"
        )
        assert request.PartitionKey == "pk1"
        assert request.RowKey == "rk1"
    
    def test_update_request_to_entity(self):
        """Test converting update request to entity."""
        request = UpdateEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            UpdatedProperty="updated"
        )
        
        entity = request.to_entity()
        assert entity.PartitionKey == "pk1"
        assert entity.RowKey == "rk1"
        assert entity.get_custom_properties()["UpdatedProperty"] == "updated"


class TestMergeEntityRequest:
    """Tests for MergeEntityRequest model."""
    
    def test_create_merge_request(self):
        """Test creating merge request."""
        request = MergeEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            Property1="value1"
        )
        assert request.PartitionKey == "pk1"
        assert request.RowKey == "rk1"
    
    def test_merge_request_without_keys(self):
        """Test creating merge request without keys (from URL)."""
        request = MergeEntityRequest(
            Property1="value1",
            Property2="value2"
        )
        assert request.PartitionKey is None
        assert request.RowKey is None
    
    def test_get_properties_to_merge(self):
        """Test getting properties to merge."""
        request = MergeEntityRequest(
            PartitionKey="pk1",
            RowKey="rk1",
            Property1="value1",
            Property2=42
        )
        
        props = request.get_properties_to_merge()
        assert "Property1" in props
        assert "Property2" in props
        assert props["Property1"] == "value1"
        assert props["Property2"] == 42
