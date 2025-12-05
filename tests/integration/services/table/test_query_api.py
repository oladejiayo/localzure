"""
Integration tests for Table Storage query API endpoints.

Tests query operations with $filter, $select, $top parameters.
"""

import pytest
import json
import base64
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


@pytest.fixture
def populated_table(client):
    """Create table with test data."""
    # Create table
    client.post("/table/testaccount/Tables", json={"TableName": "Products"})
    
    # Insert test entities
    test_data = [
        {"PartitionKey": "Electronics", "RowKey": "001", "Name": "Laptop", "Price": 999, "Stock": 50, "Active": True},
        {"PartitionKey": "Electronics", "RowKey": "002", "Name": "Mouse", "Price": 25, "Stock": 200, "Active": True},
        {"PartitionKey": "Electronics", "RowKey": "003", "Name": "Keyboard", "Price": 75, "Stock": 100, "Active": True},
        {"PartitionKey": "Books", "RowKey": "001", "Name": "Python Guide", "Price": 45, "Stock": 30, "Active": True},
        {"PartitionKey": "Books", "RowKey": "002", "Name": "Azure Book", "Price": 55, "Stock": 20, "Active": False},
        {"PartitionKey": "Furniture", "RowKey": "001", "Name": "Desk", "Price": 300, "Stock": 15, "Active": True},
        {"PartitionKey": "Furniture", "RowKey": "002", "Name": "Chair", "Price": 150, "Stock": 40, "Active": True},
    ]
    
    for data in test_data:
        client.post("/table/testaccount/Products", json=data)
    
    return "Products"


class TestQueryBasic:
    """Tests for basic query operations."""
    
    def test_query_all_entities(self, client, populated_table):
        """Test querying all entities."""
        response = client.get("/table/testaccount/Products()")
        
        assert response.status_code == 200
        data = response.json()
        assert "value" in data
        assert len(data["value"]) == 7
        assert "odata.metadata" in data
    
    def test_query_empty_table(self, client):
        """Test querying empty table."""
        client.post("/table/testaccount/Tables", json={"TableName": "EmptyTable"})
        
        response = client.get("/table/testaccount/EmptyTable()")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 0
    
    def test_query_nonexistent_table(self, client):
        """Test querying non-existent table."""
        response = client.get("/table/testaccount/NonExistent()")
        
        assert response.status_code == 404
        assert "TableNotFound" in response.text


class TestQueryFilter:
    """Tests for $filter parameter."""
    
    def test_query_filter_eq(self, client, populated_table):
        """Test filter with equality."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "PartitionKey eq 'Electronics'"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 3
        assert all(e["PartitionKey"] == "Electronics" for e in data["value"])
    
    def test_query_filter_gt(self, client, populated_table):
        """Test filter with greater than."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "Price gt 100"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 3  # Laptop (999), Desk (300), Chair (150)
        assert all(e["Price"] > 100 for e in data["value"])
    
    def test_query_filter_le(self, client, populated_table):
        """Test filter with less than or equal."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "Price le 50"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 2  # Mouse (25), Python Guide (45)
        assert all(e["Price"] <= 50 for e in data["value"])
    
    def test_query_filter_and(self, client, populated_table):
        """Test filter with AND operator."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "PartitionKey eq 'Electronics' and Price gt 50"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 2  # Laptop (999), Keyboard (75)
        for entity in data["value"]:
            assert entity["PartitionKey"] == "Electronics"
            assert entity["Price"] > 50
    
    def test_query_filter_or(self, client, populated_table):
        """Test filter with OR operator."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "PartitionKey eq 'Books' or PartitionKey eq 'Furniture'"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 4
        partitions = [e["PartitionKey"] for e in data["value"]]
        assert all(p in ["Books", "Furniture"] for p in partitions)
    
    def test_query_filter_boolean(self, client, populated_table):
        """Test filter with boolean value."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "Active eq true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 6
        assert all(e["Active"] is True for e in data["value"])
    
    def test_query_filter_complex(self, client, populated_table):
        """Test complex filter expression."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "(Price gt 50 and Price lt 200) or Stock gt 150"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should get: Keyboard (75), Azure Book (55), Chair (150), Mouse (stock 200) = 4 entities
        assert len(data["value"]) == 4
class TestQuerySelect:
    """Tests for $select parameter."""
    
    def test_query_select_single_property(self, client, populated_table):
        """Test selecting single property."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"select": "Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 7
        
        for entity in data["value"]:
            # System properties always present
            assert "PartitionKey" in entity
            assert "RowKey" in entity
            # Selected property present
            assert "Name" in entity
            # Other properties not present
            assert "Price" not in entity
            assert "Stock" not in entity
    
    def test_query_select_multiple_properties(self, client, populated_table):
        """Test selecting multiple properties."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"select": "Name,Price"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for entity in data["value"]:
            assert "Name" in entity
            assert "Price" in entity
            assert "Stock" not in entity
    
    def test_query_select_with_filter(self, client, populated_table):
        """Test $select combined with $filter."""
        response = client.get(
            "/table/testaccount/Products()",
            params={
                "filter": "PartitionKey eq 'Electronics'",
                "select": "Name,Price"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 3
        
        for entity in data["value"]:
            assert entity["PartitionKey"] == "Electronics"
            assert "Name" in entity
            assert "Price" in entity
            assert "Stock" not in entity


class TestQueryTop:
    """Tests for $top parameter."""
    
    def test_query_top(self, client, populated_table):
        """Test $top limits results."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"top": 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 3
        
        # Should have continuation token
        assert "x-ms-continuation-NextPartitionKey" in response.headers
    
    def test_query_top_larger_than_results(self, client, populated_table):
        """Test $top larger than result count."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"top": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 7  # All results
        
        # No continuation token needed
        assert "x-ms-continuation-NextPartitionKey" not in response.headers
    
    def test_query_top_with_filter(self, client, populated_table):
        """Test $top with $filter."""
        response = client.get(
            "/table/testaccount/Products()",
            params={
                "filter": "Price gt 50",
                "top": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 2
        assert all(e["Price"] > 50 for e in data["value"])


class TestQueryPagination:
    """Tests for pagination with continuation tokens."""
    
    def test_query_pagination(self, client, populated_table):
        """Test pagination with continuation token."""
        # First page
        response1 = client.get(
            "/table/testaccount/Products()",
            params={"top": 3}
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["value"]) == 3
        
        # Get continuation token
        token = response1.headers.get("x-ms-continuation-NextPartitionKey")
        assert token is not None
        
        # Decode token to get NextPartitionKey and NextRowKey
        token_data = json.loads(base64.b64decode(token).decode())
        next_pk = token_data["NextPartitionKey"]
        next_rk = token_data["NextRowKey"]
        
        # Second page
        response2 = client.get(
            "/table/testaccount/Products()",
            params={
                "top": 3,
                "NextPartitionKey": next_pk,
                "NextRowKey": next_rk
            }
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["value"]) == 3
        
        # Verify no duplicates (check full keys, not just RowKey)
        keys_1 = [(e["PartitionKey"], e["RowKey"]) for e in data1["value"]]
        keys_2 = [(e["PartitionKey"], e["RowKey"]) for e in data2["value"]]
        assert len(set(keys_1) & set(keys_2)) == 0  # No overlap
    
    def test_query_pagination_last_page(self, client, populated_table):
        """Test last page has no continuation token."""
        # Get first page
        response1 = client.get(
            "/table/testaccount/Products()",
            params={"top": 5}
        )
        
        token = response1.headers.get("x-ms-continuation-NextPartitionKey")
        token_data = json.loads(base64.b64decode(token).decode())
        
        # Get last page
        response2 = client.get(
            "/table/testaccount/Products()",
            params={
                "top": 5,
                "NextPartitionKey": token_data["NextPartitionKey"],
                "NextRowKey": token_data["NextRowKey"]
            }
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["value"]) == 2  # Remaining entities
        
        # No continuation token
        assert "x-ms-continuation-NextPartitionKey" not in response2.headers


class TestQueryCombined:
    """Tests for combined query parameters."""
    
    def test_query_filter_select_top(self, client, populated_table):
        """Test combining $filter, $select, and $top."""
        response = client.get(
            "/table/testaccount/Products()",
            params={
                "filter": "Price gt 50",
                "select": "Name,Price",
                "top": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 2
        
        for entity in data["value"]:
            assert "Name" in entity
            assert "Price" in entity
            assert entity["Price"] > 50
            assert "Stock" not in entity
    
    def test_query_all_parameters_with_pagination(self, client, populated_table):
        """Test all parameters with pagination."""
        # First page
        response1 = client.get(
            "/table/testaccount/Products()",
            params={
                "filter": "Active eq true",
                "select": "Name,Price",
                "top": 3
            }
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["value"]) == 3
        
        for entity in data1["value"]:
            assert "Name" in entity
            assert "Price" in entity
            assert "Stock" not in entity
        
        # Continuation token should be present
        assert "x-ms-continuation-NextPartitionKey" in response1.headers


class TestQueryPerformance:
    """Tests for query performance optimizations."""
    
    def test_query_point_query(self, client, populated_table):
        """Test point query (most efficient)."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "PartitionKey eq 'Electronics' and RowKey eq '001'"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 1
        assert data["value"][0]["Name"] == "Laptop"
    
    def test_query_partition_scan(self, client, populated_table):
        """Test partition scan."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "PartitionKey eq 'Books'"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 2
        assert all(e["PartitionKey"] == "Books" for e in data["value"])
    
    def test_query_table_scan(self, client, populated_table):
        """Test full table scan."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "Stock gt 100"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should work even though it requires scanning all entities
        assert len(data["value"]) == 1  # Mouse with stock 200


class TestQueryEdgeCases:
    """Tests for edge cases."""
    
    def test_query_no_parameters(self, client, populated_table):
        """Test query with no parameters."""
        response = client.get("/table/testaccount/Products()")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 7
    
    def test_query_no_matching_results(self, client, populated_table):
        """Test query with no matching results."""
        response = client.get(
            "/table/testaccount/Products()",
            params={"filter": "Price gt 10000"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 0
    
    def test_query_invalid_continuation_token(self, client, populated_table):
        """Test query with invalid continuation token."""
        # Should still work, just start from beginning
        response = client.get(
            "/table/testaccount/Products()",
            params={
                "NextPartitionKey": "InvalidKey",
                "NextRowKey": "InvalidRow"
            }
        )
        
        assert response.status_code == 200
