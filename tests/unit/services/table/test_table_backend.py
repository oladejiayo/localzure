"""
Unit tests for Table Storage backend.

Tests backend operations for tables and entities.
"""

import pytest
from datetime import datetime, timezone

from localzure.services.table.backend import (
    TableBackend,
    TableAlreadyExistsError,
    TableNotFoundError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ETagMismatchError,
)
from localzure.services.table.models import Entity


@pytest.fixture
async def backend():
    """Create a fresh backend for each test."""
    backend_instance = TableBackend()
    await backend_instance.reset()
    return backend_instance


@pytest.fixture
async def backend_with_table(backend):
    """Create backend with one table."""
    await backend.create_table("testtable")
    return backend


class TestCreateTable:
    """Tests for create_table operation."""
    
    @pytest.mark.asyncio
    async def test_create_table(self, backend):
        """Test creating a table."""
        table = await backend.create_table("MyTable")
        assert table.table_name == "MyTable"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_table(self, backend):
        """Test creating duplicate table."""
        await backend.create_table("MyTable")
        
        with pytest.raises(TableAlreadyExistsError) as exc_info:
            await backend.create_table("MyTable")
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_table_case_insensitive(self, backend):
        """Test table name case-insensitivity."""
        await backend.create_table("MyTable")
        
        with pytest.raises(TableAlreadyExistsError):
            await backend.create_table("mytable")
        
        with pytest.raises(TableAlreadyExistsError):
            await backend.create_table("MYTABLE")


class TestDeleteTable:
    """Tests for delete_table operation."""
    
    @pytest.mark.asyncio
    async def test_delete_table(self, backend_with_table):
        """Test deleting a table."""
        await backend_with_table.delete_table("testtable")
        
        tables = await backend_with_table.list_tables()
        assert len(tables) == 0
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_table(self, backend):
        """Test deleting non-existent table."""
        with pytest.raises(TableNotFoundError) as exc_info:
            await backend.delete_table("nonexistent")
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_table_with_entities(self, backend_with_table):
        """Test deleting table removes all entities."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        await backend_with_table.delete_table("testtable")
        
        tables = await backend_with_table.list_tables()
        assert len(tables) == 0


class TestListTables:
    """Tests for list_tables operation."""
    
    @pytest.mark.asyncio
    async def test_list_empty_tables(self, backend):
        """Test listing tables when none exist."""
        tables = await backend.list_tables()
        assert len(tables) == 0
    
    @pytest.mark.asyncio
    async def test_list_single_table(self, backend_with_table):
        """Test listing single table."""
        tables = await backend_with_table.list_tables()
        assert len(tables) == 1
        assert tables[0].table_name == "testtable"
    
    @pytest.mark.asyncio
    async def test_list_multiple_tables(self, backend):
        """Test listing multiple tables."""
        await backend.create_table("table1")
        await backend.create_table("table2")
        await backend.create_table("table3")
        
        tables = await backend.list_tables()
        assert len(tables) == 3
        table_names = [t.table_name for t in tables]
        assert "table1" in table_names
        assert "table2" in table_names
        assert "table3" in table_names


class TestInsertEntity:
    """Tests for insert_entity operation."""
    
    @pytest.mark.asyncio
    async def test_insert_entity(self, backend_with_table):
        """Test inserting an entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Test")
        
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        assert inserted.PartitionKey == "pk1"
        assert inserted.RowKey == "rk1"
        assert inserted.etag != ""
        assert isinstance(inserted.Timestamp, datetime)
        assert inserted.get_custom_properties()["Name"] == "Test"
    
    @pytest.mark.asyncio
    async def test_insert_entity_generates_timestamp(self, backend_with_table):
        """Test that insert generates timestamp."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        assert isinstance(inserted.Timestamp, datetime)
        assert inserted.Timestamp.tzinfo == timezone.utc
    
    @pytest.mark.asyncio
    async def test_insert_entity_generates_etag(self, backend_with_table):
        """Test that insert generates ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        assert inserted.etag != ""
        assert inserted.etag.startswith('W/"datetime\'')
    
    @pytest.mark.asyncio
    async def test_insert_duplicate_entity(self, backend_with_table):
        """Test inserting duplicate entity."""
        entity1 = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity1)
        
        entity2 = Entity(PartitionKey="pk1", RowKey="rk1")
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            await backend_with_table.insert_entity("testtable", entity2)
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_insert_entity_table_not_found(self, backend):
        """Test inserting entity to non-existent table."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        
        with pytest.raises(TableNotFoundError):
            await backend.insert_entity("nonexistent", entity)


class TestGetEntity:
    """Tests for get_entity operation."""
    
    @pytest.mark.asyncio
    async def test_get_entity(self, backend_with_table):
        """Test getting an entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Test")
        await backend_with_table.insert_entity("testtable", entity)
        
        retrieved = await backend_with_table.get_entity("testtable", "pk1", "rk1")
        
        assert retrieved.PartitionKey == "pk1"
        assert retrieved.RowKey == "rk1"
        assert retrieved.get_custom_properties()["Name"] == "Test"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_entity(self, backend_with_table):
        """Test getting non-existent entity."""
        with pytest.raises(EntityNotFoundError) as exc_info:
            await backend_with_table.get_entity("testtable", "pk1", "rk1")
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_entity_table_not_found(self, backend):
        """Test getting entity from non-existent table."""
        with pytest.raises(TableNotFoundError):
            await backend.get_entity("nonexistent", "pk1", "rk1")


class TestUpdateEntity:
    """Tests for update_entity operation."""
    
    @pytest.mark.asyncio
    async def test_update_entity(self, backend_with_table):
        """Test updating an entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Original")
        await backend_with_table.insert_entity("testtable", entity)
        
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Updated")
        result = await backend_with_table.update_entity(
            "testtable", "pk1", "rk1", updated_entity
        )
        
        assert result.get_custom_properties()["Name"] == "Updated"
        assert result.etag != entity.etag
    
    @pytest.mark.asyncio
    async def test_update_entity_replaces_all_properties(self, backend_with_table):
        """Test that update replaces all properties."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Prop1="val1", Prop2="val2")
        await backend_with_table.insert_entity("testtable", entity)
        
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1", Prop3="val3")
        result = await backend_with_table.update_entity(
            "testtable", "pk1", "rk1", updated_entity
        )
        
        custom_props = result.get_custom_properties()
        assert "Prop3" in custom_props
        assert "Prop1" not in custom_props
        assert "Prop2" not in custom_props
    
    @pytest.mark.asyncio
    async def test_update_entity_with_etag(self, backend_with_table):
        """Test updating entity with ETag validation."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Updated")
        result = await backend_with_table.update_entity(
            "testtable", "pk1", "rk1", updated_entity, if_match=inserted.etag
        )
        
        assert result.get_custom_properties()["Name"] == "Updated"
    
    @pytest.mark.asyncio
    async def test_update_entity_etag_mismatch(self, backend_with_table):
        """Test updating entity with mismatched ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1")
        with pytest.raises(ETagMismatchError):
            await backend_with_table.update_entity(
                "testtable", "pk1", "rk1", updated_entity, if_match="wrong-etag"
            )
    
    @pytest.mark.asyncio
    async def test_update_entity_wildcard_etag(self, backend_with_table):
        """Test updating entity with wildcard ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Updated")
        result = await backend_with_table.update_entity(
            "testtable", "pk1", "rk1", updated_entity, if_match="*"
        )
        
        assert result.get_custom_properties()["Name"] == "Updated"
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_entity(self, backend_with_table):
        """Test updating non-existent entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.update_entity("testtable", "pk1", "rk1", entity)


class TestMergeEntity:
    """Tests for merge_entity operation."""
    
    @pytest.mark.asyncio
    async def test_merge_entity(self, backend_with_table):
        """Test merging an entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Prop1="val1", Prop2="val2")
        await backend_with_table.insert_entity("testtable", entity)
        
        properties = {"Prop2": "updated", "Prop3": "new"}
        result = await backend_with_table.merge_entity(
            "testtable", "pk1", "rk1", properties
        )
        
        custom_props = result.get_custom_properties()
        assert custom_props["Prop1"] == "val1"  # Unchanged
        assert custom_props["Prop2"] == "updated"  # Updated
        assert custom_props["Prop3"] == "new"  # New
    
    @pytest.mark.asyncio
    async def test_merge_entity_preserves_unspecified_properties(self, backend_with_table):
        """Test that merge preserves unspecified properties."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Prop1="val1", Prop2="val2")
        await backend_with_table.insert_entity("testtable", entity)
        
        properties = {"Prop3": "val3"}
        result = await backend_with_table.merge_entity(
            "testtable", "pk1", "rk1", properties
        )
        
        custom_props = result.get_custom_properties()
        assert "Prop1" in custom_props
        assert "Prop2" in custom_props
        assert "Prop3" in custom_props
    
    @pytest.mark.asyncio
    async def test_merge_entity_with_etag(self, backend_with_table):
        """Test merging entity with ETag validation."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Prop1="val1")
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        properties = {"Prop2": "val2"}
        result = await backend_with_table.merge_entity(
            "testtable", "pk1", "rk1", properties, if_match=inserted.etag
        )
        
        custom_props = result.get_custom_properties()
        assert custom_props["Prop1"] == "val1"
        assert custom_props["Prop2"] == "val2"
    
    @pytest.mark.asyncio
    async def test_merge_entity_etag_mismatch(self, backend_with_table):
        """Test merging entity with mismatched ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        properties = {"Prop1": "val1"}
        with pytest.raises(ETagMismatchError):
            await backend_with_table.merge_entity(
                "testtable", "pk1", "rk1", properties, if_match="wrong-etag"
            )
    
    @pytest.mark.asyncio
    async def test_merge_nonexistent_entity(self, backend_with_table):
        """Test merging non-existent entity."""
        properties = {"Prop1": "val1"}
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.merge_entity("testtable", "pk1", "rk1", properties)


class TestDeleteEntity:
    """Tests for delete_entity operation."""
    
    @pytest.mark.asyncio
    async def test_delete_entity(self, backend_with_table):
        """Test deleting an entity."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        await backend_with_table.delete_entity("testtable", "pk1", "rk1")
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.get_entity("testtable", "pk1", "rk1")
    
    @pytest.mark.asyncio
    async def test_delete_entity_with_etag(self, backend_with_table):
        """Test deleting entity with ETag validation."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        inserted = await backend_with_table.insert_entity("testtable", entity)
        
        await backend_with_table.delete_entity(
            "testtable", "pk1", "rk1", if_match=inserted.etag
        )
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.get_entity("testtable", "pk1", "rk1")
    
    @pytest.mark.asyncio
    async def test_delete_entity_etag_mismatch(self, backend_with_table):
        """Test deleting entity with mismatched ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        with pytest.raises(ETagMismatchError):
            await backend_with_table.delete_entity(
                "testtable", "pk1", "rk1", if_match="wrong-etag"
            )
    
    @pytest.mark.asyncio
    async def test_delete_entity_wildcard_etag(self, backend_with_table):
        """Test deleting entity with wildcard ETag."""
        entity = Entity(PartitionKey="pk1", RowKey="rk1")
        await backend_with_table.insert_entity("testtable", entity)
        
        await backend_with_table.delete_entity("testtable", "pk1", "rk1", if_match="*")
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.get_entity("testtable", "pk1", "rk1")
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_entity(self, backend_with_table):
        """Test deleting non-existent entity."""
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.delete_entity("testtable", "pk1", "rk1")


class TestEntityIntegration:
    """Integration tests for entity operations."""
    
    @pytest.mark.asyncio
    async def test_insert_get_update_delete_workflow(self, backend_with_table):
        """Test complete entity lifecycle."""
        # Insert
        entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Original")
        inserted = await backend_with_table.insert_entity("testtable", entity)
        assert inserted.get_custom_properties()["Name"] == "Original"
        
        # Get
        retrieved = await backend_with_table.get_entity("testtable", "pk1", "rk1")
        assert retrieved.PartitionKey == "pk1"
        
        # Update
        updated_entity = Entity(PartitionKey="pk1", RowKey="rk1", Name="Updated")
        updated = await backend_with_table.update_entity(
            "testtable", "pk1", "rk1", updated_entity
        )
        assert updated.get_custom_properties()["Name"] == "Updated"
        
        # Delete
        await backend_with_table.delete_entity("testtable", "pk1", "rk1")
        
        with pytest.raises(EntityNotFoundError):
            await backend_with_table.get_entity("testtable", "pk1", "rk1")
    
    @pytest.mark.asyncio
    async def test_multiple_entities_same_partition(self, backend_with_table):
        """Test multiple entities in same partition."""
        entity1 = Entity(PartitionKey="pk1", RowKey="rk1", Value=1)
        entity2 = Entity(PartitionKey="pk1", RowKey="rk2", Value=2)
        entity3 = Entity(PartitionKey="pk1", RowKey="rk3", Value=3)
        
        await backend_with_table.insert_entity("testtable", entity1)
        await backend_with_table.insert_entity("testtable", entity2)
        await backend_with_table.insert_entity("testtable", entity3)
        
        retrieved1 = await backend_with_table.get_entity("testtable", "pk1", "rk1")
        retrieved2 = await backend_with_table.get_entity("testtable", "pk1", "rk2")
        retrieved3 = await backend_with_table.get_entity("testtable", "pk1", "rk3")
        
        assert retrieved1.get_custom_properties()["Value"] == 1
        assert retrieved2.get_custom_properties()["Value"] == 2
        assert retrieved3.get_custom_properties()["Value"] == 3
