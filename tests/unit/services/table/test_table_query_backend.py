"""
Unit tests for Table Storage backend query operations.

Tests query_entities method with filtering, projection, pagination.
"""

import pytest
import base64
import json

from localzure.services.table.backend import TableBackend, TableNotFoundError
from localzure.services.table.models import Entity


@pytest.fixture
async def backend():
    """Create a fresh backend for each test."""
    backend = TableBackend()
    await backend.reset()
    return backend


@pytest.fixture
async def backend_with_test_data(backend):
    """Create backend with test table and entities."""
    # Create table
    await backend.create_table("testtable")
    
    # Insert test entities
    test_data = [
        {"PartitionKey": "US", "RowKey": "001", "Name": "Alice", "Age": 25, "City": "Seattle", "Active": True},
        {"PartitionKey": "US", "RowKey": "002", "Name": "Bob", "Age": 35, "City": "Portland", "Active": True},
        {"PartitionKey": "US", "RowKey": "003", "Name": "Charlie", "Age": 45, "City": "Seattle", "Active": False},
        {"PartitionKey": "EU", "RowKey": "001", "Name": "David", "Age": 30, "City": "London", "Active": True},
        {"PartitionKey": "EU", "RowKey": "002", "Name": "Eve", "Age": 28, "City": "Paris", "Active": True},
        {"PartitionKey": "EU", "RowKey": "003", "Name": "Frank", "Age": 50, "City": "Berlin", "Active": False},
        {"PartitionKey": "ASIA", "RowKey": "001", "Name": "Grace", "Age": 32, "City": "Tokyo", "Active": True},
        {"PartitionKey": "ASIA", "RowKey": "002", "Name": "Henry", "Age": 27, "City": "Seoul", "Active": True},
    ]
    
    for data in test_data:
        entity = Entity(**data)
        await backend.insert_entity("testtable", entity)
    
    return backend


class TestQueryEntitiesBasic:
    """Tests for basic query operations."""
    
    @pytest.mark.asyncio
    async def test_query_all_entities(self, backend_with_test_data):
        """Test querying all entities without filter."""
        results, token = await backend_with_test_data.query_entities("testtable")
        
        assert len(results) == 8
        assert token is None  # No continuation token for < 1000 results
    
    @pytest.mark.asyncio
    async def test_query_empty_table(self, backend):
        """Test querying empty table."""
        await backend.create_table("emptytable")
        
        results, token = await backend.query_entities("emptytable")
        
        assert len(results) == 0
        assert token is None
    
    @pytest.mark.asyncio
    async def test_query_nonexistent_table(self, backend):
        """Test querying non-existent table raises error."""
        with pytest.raises(TableNotFoundError):
            await backend.query_entities("nonexistent")


class TestQueryEntitiesFiltering:
    """Tests for $filter parameter."""
    
    @pytest.mark.asyncio
    async def test_query_filter_eq(self, backend_with_test_data):
        """Test filter with equality."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="PartitionKey eq 'US'"
        )
        
        assert len(results) == 3
        assert all(e.PartitionKey == "US" for e in results)
    
    @pytest.mark.asyncio
    async def test_query_filter_gt(self, backend_with_test_data):
        """Test filter with greater than."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="Age gt 30"
        )
        
        assert len(results) == 4
        assert all(e.get_custom_properties().get("Age", 0) > 30 for e in results)
    
    @pytest.mark.asyncio
    async def test_query_filter_and(self, backend_with_test_data):
        """Test filter with AND operator."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="PartitionKey eq 'US' and Age gt 30"
        )
        
        assert len(results) == 2  # Bob (35) and Charlie (45)
        for entity in results:
            assert entity.PartitionKey == "US"
            assert entity.get_custom_properties().get("Age", 0) > 30
    
    @pytest.mark.asyncio
    async def test_query_filter_or(self, backend_with_test_data):
        """Test filter with OR operator."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="City eq 'Seattle' or City eq 'London'"
        )
        
        assert len(results) == 3  # Alice, Charlie, David
        cities = [e.get_custom_properties().get("City") for e in results]
        assert all(c in ["Seattle", "London"] for c in cities)
    
    @pytest.mark.asyncio
    async def test_query_filter_boolean(self, backend_with_test_data):
        """Test filter with boolean value."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="Active eq true"
        )
        
        assert len(results) == 6
        assert all(e.get_custom_properties().get("Active") is True for e in results)
    
    @pytest.mark.asyncio
    async def test_query_filter_complex(self, backend_with_test_data):
        """Test complex filter expression."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="(PartitionKey eq 'US' or PartitionKey eq 'EU') and Age gt 28 and Active eq true"
        )
        
        # Should get: Bob (US, 35, true), David (EU, 30, true)
        assert len(results) == 2
        partition_keys = [e.PartitionKey for e in results]
        assert "US" in partition_keys or "EU" in partition_keys


class TestQueryEntitiesProjection:
    """Tests for $select parameter."""
    
    @pytest.mark.asyncio
    async def test_query_select_single_property(self, backend_with_test_data):
        """Test selecting single property."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            select="Name"
        )
        
        assert len(results) == 8
        for entity in results:
            entity_dict = entity.to_dict()
            # System properties always present
            assert "PartitionKey" in entity_dict
            assert "RowKey" in entity_dict
            # Selected property present
            assert "Name" in entity_dict
            # Other properties not present
            assert "Age" not in entity_dict
            assert "City" not in entity_dict
    
    @pytest.mark.asyncio
    async def test_query_select_multiple_properties(self, backend_with_test_data):
        """Test selecting multiple properties."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            select="Name,Age"
        )
        
        assert len(results) == 8
        for entity in results:
            entity_dict = entity.to_dict()
            assert "Name" in entity_dict
            assert "Age" in entity_dict
            assert "City" not in entity_dict
    
    @pytest.mark.asyncio
    async def test_query_select_with_filter(self, backend_with_test_data):
        """Test $select combined with $filter."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="Age gt 30",
            select="Name,Age"
        )
        
        assert len(results) == 4
        for entity in results:
            entity_dict = entity.to_dict()
            assert "Name" in entity_dict
            assert "Age" in entity_dict
            assert entity_dict["Age"] > 30


class TestQueryEntitiesPagination:
    """Tests for $top parameter and pagination."""
    
    @pytest.mark.asyncio
    async def test_query_top(self, backend_with_test_data):
        """Test $top limits results."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            top=3
        )
        
        assert len(results) == 3
        assert token is not None  # Should have continuation token
    
    @pytest.mark.asyncio
    async def test_query_top_larger_than_results(self, backend_with_test_data):
        """Test $top larger than result count."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            top=100
        )
        
        assert len(results) == 8  # All results
        assert token is None  # No continuation token needed
    
    @pytest.mark.asyncio
    async def test_query_pagination_with_continuation_token(self, backend_with_test_data):
        """Test pagination with continuation token."""
        # First page
        results1, token1 = await backend_with_test_data.query_entities(
            "testtable",
            top=3
        )
        
        assert len(results1) == 3
        assert token1 is not None
        
        # Decode continuation token
        token_data = json.loads(base64.b64decode(token1).decode())
        next_pk = token_data["NextPartitionKey"]
        next_rk = token_data["NextRowKey"]
        
        # Second page
        results2, token2 = await backend_with_test_data.query_entities(
            "testtable",
            top=3,
            next_partition_key=next_pk,
            next_row_key=next_rk
        )
        
        assert len(results2) == 3
        assert token2 is not None
        
        # Third page (remaining 2)
        token_data2 = json.loads(base64.b64decode(token2).decode())
        results3, token3 = await backend_with_test_data.query_entities(
            "testtable",
            top=3,
            next_partition_key=token_data2["NextPartitionKey"],
            next_row_key=token_data2["NextRowKey"]
        )
        
        assert len(results3) == 2
        assert token3 is None  # No more results
        
        # Verify no duplicates
        all_keys = []
        for r in [results1, results2, results3]:
            all_keys.extend([(e.PartitionKey, e.RowKey) for e in r])
        assert len(all_keys) == len(set(all_keys))  # No duplicates
    
    @pytest.mark.asyncio
    async def test_query_default_top_limit(self, backend):
        """Test default $top limit of 1000."""
        # Create table with 1500 entities
        await backend.create_table("largetable")
        
        for i in range(1500):
            entity = Entity(
                PartitionKey="partition1",
                RowKey=f"row{i:04d}",
                Value=i
            )
            await backend.insert_entity("largetable", entity)
        
        # Query without explicit $top
        results, token = await backend.query_entities("largetable")
        
        assert len(results) == 1000  # Default limit
        assert token is not None  # Should have more results


class TestQueryEntitiesPerformance:
    """Tests for query performance paths."""
    
    @pytest.mark.asyncio
    async def test_query_by_partition_key(self, backend_with_test_data):
        """Test optimized partition key query."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="PartitionKey eq 'US'"
        )
        
        assert len(results) == 3
        assert all(e.PartitionKey == "US" for e in results)
    
    @pytest.mark.asyncio
    async def test_query_by_partition_and_row_key(self, backend_with_test_data):
        """Test point query (most efficient)."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="PartitionKey eq 'US' and RowKey eq '001'"
        )
        
        assert len(results) == 1
        assert results[0].PartitionKey == "US"
        assert results[0].RowKey == "001"
    
    @pytest.mark.asyncio
    async def test_query_table_scan(self, backend_with_test_data):
        """Test table scan (least efficient)."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="City eq 'Seattle'"
        )
        
        # Still works, just scans all entities
        assert len(results) == 2


class TestQueryEntitiesCombined:
    """Tests for combined query parameters."""
    
    @pytest.mark.asyncio
    async def test_query_filter_select_top(self, backend_with_test_data):
        """Test combining $filter, $select, and $top."""
        results, token = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="Age gt 28",
            select="Name,Age",
            top=3
        )
        
        assert len(results) == 3
        assert token is not None
        
        for entity in results:
            entity_dict = entity.to_dict()
            assert "Name" in entity_dict
            assert "Age" in entity_dict
            assert entity_dict["Age"] > 28
            assert "City" not in entity_dict
    
    @pytest.mark.asyncio
    async def test_query_pagination_with_filter(self, backend_with_test_data):
        """Test pagination with filter."""
        # First page with filter
        results1, token1 = await backend_with_test_data.query_entities(
            "testtable",
            filter_expr="Active eq true",
            top=3
        )
        
        assert len(results1) == 3
        assert all(e.get_custom_properties().get("Active") is True for e in results1)
        
        # Second page
        if token1:
            token_data = json.loads(base64.b64decode(token1).decode())
            results2, token2 = await backend_with_test_data.query_entities(
                "testtable",
                filter_expr="Active eq true",
                top=3,
                next_partition_key=token_data["NextPartitionKey"],
                next_row_key=token_data["NextRowKey"]
            )
            
            assert len(results2) == 3
            assert all(e.get_custom_properties().get("Active") is True for e in results2)
