"""
Integration tests for Table Storage API endpoints.

Tests table and entity HTTP API operations.
"""

import pytest
import json
from fastapi.testclient import TestClient

from localzure.services.table.api import router, backend


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_backend():
    """Reset backend before each test."""
    await backend.reset()


class TestCreateTable:
    """Tests for create table endpoint."""
    
    def test_create_table(self, client):
        """Test creating a table."""
        response = client.post(
            "/table/testaccount/Tables",
            json={"TableName": "MyTable"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["TableName"] == "MyTable"
        assert "odata.metadata" in data
    
    def test_create_table_duplicate(self, client):
        """Test creating duplicate table."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        response = client.post(
            "/table/testaccount/Tables",
            json={"TableName": "MyTable"}
        )
        
        assert response.status_code == 409
        assert "TableAlreadyExists" in response.text
    
    def test_create_table_invalid_name(self, client):
        """Test creating table with invalid name."""
        response = client.post(
            "/table/testaccount/Tables",
            json={"TableName": "my-table"}
        )
        
        assert response.status_code == 400
        assert "InvalidInput" in response.text
    
    def test_create_table_empty_name(self, client):
        """Test creating table with empty name."""
        response = client.post(
            "/table/testaccount/Tables",
            json={"TableName": ""}
        )
        
        assert response.status_code == 400


class TestListTables:
    """Tests for list tables endpoint."""
    
    def test_list_empty_tables(self, client):
        """Test listing tables when none exist."""
        response = client.get("/table/testaccount/Tables")
        
        assert response.status_code == 200
        data = response.json()
        assert "value" in data
        assert len(data["value"]) == 0
    
    def test_list_single_table(self, client):
        """Test listing single table."""
        client.post("/table/testaccount/Tables", json={"TableName": "Table1"})
        
        response = client.get("/table/testaccount/Tables")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 1
        assert data["value"][0]["TableName"] == "Table1"
    
    def test_list_multiple_tables(self, client):
        """Test listing multiple tables."""
        client.post("/table/testaccount/Tables", json={"TableName": "Table1"})
        client.post("/table/testaccount/Tables", json={"TableName": "Table2"})
        client.post("/table/testaccount/Tables", json={"TableName": "Table3"})
        
        response = client.get("/table/testaccount/Tables")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 3
        table_names = [t["TableName"] for t in data["value"]]
        assert "Table1" in table_names
        assert "Table2" in table_names
        assert "Table3" in table_names


class TestDeleteTable:
    """Tests for delete table endpoint."""
    
    def test_delete_table(self, client):
        """Test deleting a table."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        response = client.delete("/table/testaccount/Tables('MyTable')")
        
        assert response.status_code == 204
    
    def test_delete_nonexistent_table(self, client):
        """Test deleting non-existent table."""
        response = client.delete("/table/testaccount/Tables('nonexistent')")
        
        assert response.status_code == 404
        assert "TableNotFound" in response.text


class TestInsertEntity:
    """Tests for insert entity endpoint."""
    
    def test_insert_entity(self, client):
        """Test inserting an entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Name": "John Doe",
            "Age": 30
        }
        response = client.post(
            "/table/testaccount/MyTable",
            json=entity_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["PartitionKey"] == "pk1"
        assert data["RowKey"] == "rk1"
        assert data["Name"] == "John Doe"
        assert data["Age"] == 30
        assert "Timestamp" in data
        assert "odata.etag" in data
        assert "ETag" in response.headers
    
    def test_insert_entity_duplicate(self, client):
        """Test inserting duplicate entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        response = client.post("/table/testaccount/MyTable", json=entity_data)
        
        assert response.status_code == 409
        assert "EntityAlreadyExists" in response.text
    
    def test_insert_entity_table_not_found(self, client):
        """Test inserting entity to non-existent table."""
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        response = client.post("/table/testaccount/nonexistent", json=entity_data)
        
        assert response.status_code == 404
        assert "TableNotFound" in response.text


class TestGetEntity:
    """Tests for get entity endpoint."""
    
    def test_get_entity(self, client):
        """Test getting an entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Name": "Test"
        }
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        
        assert response.status_code == 200
        data = response.json()
        assert data["PartitionKey"] == "pk1"
        assert data["RowKey"] == "rk1"
        assert data["Name"] == "Test"
        assert "ETag" in response.headers
    
    def test_get_nonexistent_entity(self, client):
        """Test getting non-existent entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        
        assert response.status_code == 404
        assert "ResourceNotFound" in response.text
    
    def test_get_entity_table_not_found(self, client):
        """Test getting entity from non-existent table."""
        response = client.get("/table/testaccount/nonexistent(PartitionKey='pk1',RowKey='rk1')")
        
        assert response.status_code == 404
        assert "TableNotFound" in response.text


class TestUpdateEntity:
    """Tests for update entity endpoint."""
    
    def test_update_entity(self, client):
        """Test updating an entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Name": "Original"}
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Update entity
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Name": "Updated"}
        response = client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data
        )
        
        assert response.status_code == 204
        assert "ETag" in response.headers
        
        # Verify update
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        data = get_response.json()
        assert data["Name"] == "Updated"
    
    def test_update_entity_replaces_properties(self, client):
        """Test that update replaces all properties."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity with multiple properties
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Prop1": "val1",
            "Prop2": "val2"
        }
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Update with different properties
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Prop3": "val3"}
        client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data
        )
        
        # Verify old properties are gone
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        data = get_response.json()
        assert "Prop3" in data
        assert "Prop1" not in data
        assert "Prop2" not in data
    
    def test_update_entity_with_etag(self, client):
        """Test updating entity with ETag validation."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        insert_response = client.post("/table/testaccount/MyTable", json=entity_data)
        etag = insert_response.headers["ETag"]
        
        # Update with correct ETag
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Name": "Updated"}
        response = client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data,
            headers={"If-Match": etag}
        )
        
        assert response.status_code == 204
    
    def test_update_entity_etag_mismatch(self, client):
        """Test updating entity with mismatched ETag."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Update with wrong ETag
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Name": "Updated"}
        response = client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data,
            headers={"If-Match": "wrong-etag"}
        )
        
        assert response.status_code == 412
        assert "UpdateConditionNotSatisfied" in response.text
    
    def test_update_nonexistent_entity(self, client):
        """Test updating non-existent entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        response = client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data
        )
        
        assert response.status_code == 404


class TestMergeEntity:
    """Tests for merge entity endpoint."""
    
    def test_merge_entity(self, client):
        """Test merging an entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Prop1": "val1",
            "Prop2": "val2"
        }
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Merge with new property
        merge_data = {"Prop2": "updated", "Prop3": "new"}
        response = client.patch(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=merge_data
        )
        
        assert response.status_code == 204
        
        # Verify merge preserved Prop1 and updated Prop2
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        data = get_response.json()
        assert data["Prop1"] == "val1"  # Unchanged
        assert data["Prop2"] == "updated"  # Updated
        assert data["Prop3"] == "new"  # New
    
    def test_merge_entity_preserves_properties(self, client):
        """Test that merge preserves unspecified properties."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Prop1": "val1",
            "Prop2": "val2"
        }
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Merge with one new property
        merge_data = {"Prop3": "val3"}
        client.patch(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=merge_data
        )
        
        # Verify all properties exist
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        data = get_response.json()
        assert "Prop1" in data
        assert "Prop2" in data
        assert "Prop3" in data
    
    def test_merge_entity_with_etag(self, client):
        """Test merging entity with ETag validation."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Prop1": "val1"}
        insert_response = client.post("/table/testaccount/MyTable", json=entity_data)
        etag = insert_response.headers["ETag"]
        
        # Merge with correct ETag
        merge_data = {"Prop2": "val2"}
        response = client.patch(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=merge_data,
            headers={"If-Match": etag}
        )
        
        assert response.status_code == 204


class TestDeleteEntity:
    """Tests for delete entity endpoint."""
    
    def test_delete_entity(self, client):
        """Test deleting an entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Delete entity
        response = client.delete(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')"
        )
        
        assert response.status_code == 204
        
        # Verify entity is gone
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        assert get_response.status_code == 404
    
    def test_delete_entity_with_etag(self, client):
        """Test deleting entity with ETag validation."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        insert_response = client.post("/table/testaccount/MyTable", json=entity_data)
        etag = insert_response.headers["ETag"]
        
        # Delete with correct ETag
        response = client.delete(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            headers={"If-Match": etag}
        )
        
        assert response.status_code == 204
    
    def test_delete_entity_etag_mismatch(self, client):
        """Test deleting entity with mismatched ETag."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {"PartitionKey": "pk1", "RowKey": "rk1"}
        client.post("/table/testaccount/MyTable", json=entity_data)
        
        # Delete with wrong ETag
        response = client.delete(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            headers={"If-Match": "wrong-etag"}
        )
        
        assert response.status_code == 412
    
    def test_delete_nonexistent_entity(self, client):
        """Test deleting non-existent entity."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        response = client.delete(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')"
        )
        
        assert response.status_code == 404


class TestTableWorkflows:
    """Integration tests for complete workflows."""
    
    def test_complete_entity_lifecycle(self, client):
        """Test insert -> get -> update -> merge -> delete."""
        # Create table
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert entity
        entity_data = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Name": "Original",
            "Age": 30
        }
        insert_response = client.post("/table/testaccount/MyTable", json=entity_data)
        assert insert_response.status_code == 201
        
        # Get entity
        get_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["Name"] == "Original"
        
        # Update entity
        updated_data = {"PartitionKey": "pk1", "RowKey": "rk1", "Name": "Updated"}
        update_response = client.put(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=updated_data
        )
        assert update_response.status_code == 204
        
        # Merge entity
        merge_data = {"Age": 31, "City": "Seattle"}
        merge_response = client.patch(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')",
            json=merge_data
        )
        assert merge_response.status_code == 204
        
        # Delete entity
        delete_response = client.delete(
            "/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')"
        )
        assert delete_response.status_code == 204
        
        # Verify gone
        final_response = client.get("/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk1')")
        assert final_response.status_code == 404
    
    def test_multiple_entities_in_table(self, client):
        """Test working with multiple entities."""
        client.post("/table/testaccount/Tables", json={"TableName": "MyTable"})
        
        # Insert 3 entities
        for i in range(1, 4):
            entity_data = {
                "PartitionKey": "pk1",
                "RowKey": f"rk{i}",
                "Value": i
            }
            response = client.post("/table/testaccount/MyTable", json=entity_data)
            assert response.status_code == 201
        
        # Verify all entities exist
        for i in range(1, 4):
            response = client.get(f"/table/testaccount/MyTable(PartitionKey='pk1',RowKey='rk{i}')")
            assert response.status_code == 200
            data = response.json()
            assert data["Value"] == i
