"""
Unit tests for Advanced OData Features.

Comprehensive test suite covering:
- $orderby with multiple keys and directions
- $skip for pagination offset
- $count for count-only queries
- $inlinecount for counts with results
- $format for response format
- $metadata for type information
- Server-side paging with continuation tokens
- Query result sets
- Query statistics
"""

import pytest
from datetime import datetime
from localzure.services.table.advanced import (
    SortDirection,
    ResponseFormat,
    ContinuationToken,
    QueryStatistics,
    ODataQueryOptions,
    QueryResultSet,
    QueryExecutor,
    parse_orderby,
    parse_query_options,
)


class TestSortDirection:
    """Tests for sort direction enum."""
    
    def test_sort_direction_values(self):
        """Test sort direction values."""
        assert str(SortDirection.ASC) == "asc"
        assert str(SortDirection.DESC) == "desc"


class TestResponseFormat:
    """Tests for response format enum."""
    
    def test_response_format_values(self):
        """Test response format values."""
        assert str(ResponseFormat.JSON) == "json"
        assert str(ResponseFormat.ATOM) == "atom"


class TestContinuationToken:
    """Tests for continuation token."""
    
    def test_create_token(self):
        """Test creating continuation token."""
        token = ContinuationToken(
            partition_key='P1',
            row_key='R1',
            skip_count=100,
            total_scanned=1000,
            query_hash='abc123'
        )
        
        assert token.partition_key == 'P1'
        assert token.row_key == 'R1'
        assert token.skip_count == 100
    
    def test_encode_decode(self):
        """Test token encoding and decoding."""
        token = ContinuationToken(
            partition_key='partition1',
            row_key='row1',
            skip_count=50,
            total_scanned=500,
            query_hash='hash123'
        )
        
        encoded = token.encode()
        assert isinstance(encoded, str)
        
        decoded = ContinuationToken.decode(encoded)
        assert decoded.partition_key == 'partition1'
        assert decoded.row_key == 'row1'
        assert decoded.skip_count == 50
        assert decoded.total_scanned == 500
        assert decoded.query_hash == 'hash123'
    
    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        with pytest.raises(ValueError):
            ContinuationToken.decode('invalid_token')


class TestQueryStatistics:
    """Tests for query statistics."""
    
    def test_create_statistics(self):
        """Test creating statistics."""
        stats = QueryStatistics(
            entities_scanned=1000,
            entities_returned=50,
            entities_filtered=950,
            execution_time_ms=15.5,
            sort_time_ms=2.3,
            cache_hit=True
        )
        
        assert stats.entities_scanned == 1000
        assert stats.entities_returned == 50
        assert stats.cache_hit is True
    
    def test_to_dict(self):
        """Test statistics serialization."""
        stats = QueryStatistics(
            entities_scanned=100,
            entities_returned=10,
            execution_time_ms=5.5
        )
        
        data = stats.to_dict()
        
        assert data['entities_scanned'] == 100
        assert data['entities_returned'] == 10
        assert data['execution_time_ms'] == 5.5


class TestODataQueryOptions:
    """Tests for query options."""
    
    def test_create_options(self):
        """Test creating query options."""
        options = ODataQueryOptions(
            filter="Price gt 50",
            select=["Name", "Price"],
            orderby=[("Price", SortDirection.DESC)],
            top=10,
            skip=20
        )
        
        assert options.filter == "Price gt 50"
        assert options.select == ["Name", "Price"]
        assert options.top == 10
        assert options.skip == 20
    
    def test_default_options(self):
        """Test default option values."""
        options = ODataQueryOptions()
        
        assert options.filter is None
        assert options.select is None
        assert options.top is None
        assert options.count is False
        assert options.format == ResponseFormat.JSON
    
    def test_top_validation(self):
        """Test $top validation."""
        with pytest.raises(ValueError):
            ODataQueryOptions(top=-1)
    
    def test_skip_validation(self):
        """Test $skip validation."""
        with pytest.raises(ValueError):
            ODataQueryOptions(skip=-1)
    
    def test_top_limit(self):
        """Test $top limit enforcement."""
        options = ODataQueryOptions(top=5000)
        
        # Should be capped at 1000
        assert options.top == 1000
    
    def test_get_hash(self):
        """Test query hash generation."""
        options1 = ODataQueryOptions(
            filter="Price gt 50",
            top=10
        )
        
        options2 = ODataQueryOptions(
            filter="Price gt 50",
            top=10
        )
        
        # Same options should have same hash
        assert options1.get_hash() == options2.get_hash()
        
        options3 = ODataQueryOptions(
            filter="Price gt 100",
            top=10
        )
        
        # Different options should have different hash
        assert options1.get_hash() != options3.get_hash()
    
    def test_to_dict(self):
        """Test options serialization."""
        options = ODataQueryOptions(
            filter="Price gt 50",
            select=["Name", "Price"],
            orderby=[("Price", SortDirection.DESC), ("Name", SortDirection.ASC)],
            top=10,
            skip=5,
            inlinecount=True
        )
        
        data = options.to_dict()
        
        assert data['$filter'] == "Price gt 50"
        assert data['$select'] == "Name,Price"
        assert data['$orderby'] == "Price desc,Name asc"
        assert data['$top'] == 10
        assert data['$skip'] == 5
        assert data['$inlinecount'] == 'allpages'


class TestQueryResultSet:
    """Tests for query result set."""
    
    def test_create_result_set(self):
        """Test creating result set."""
        entities = [
            {'PartitionKey': 'P1', 'RowKey': 'R1', 'Value': 1},
            {'PartitionKey': 'P1', 'RowKey': 'R2', 'Value': 2}
        ]
        
        result = QueryResultSet(
            entities=entities,
            count=2
        )
        
        assert len(result.entities) == 2
        assert result.count == 2
    
    def test_to_dict(self):
        """Test result set serialization."""
        entities = [{'Value': 1}]
        stats = QueryStatistics(entities_scanned=10)
        
        result = QueryResultSet(
            entities=entities,
            count=1,
            query_stats=stats
        )
        
        data = result.to_dict(include_stats=True)
        
        assert 'value' in data
        assert data['odata.count'] == 1
        assert 'query_stats' in data
    
    def test_to_dict_with_continuation(self):
        """Test result set with continuation token."""
        entities = [{'Value': 1}]
        token = ContinuationToken('P1', 'R1')
        
        result = QueryResultSet(
            entities=entities,
            continuation=token
        )
        
        data = result.to_dict()
        
        assert 'x-ms-continuation-token' in data


class TestQueryExecutor:
    """Tests for query executor."""
    
    def test_init(self):
        """Test executor initialization."""
        executor = QueryExecutor()
        
        assert executor._query_cache == {}
    
    def test_execute_no_filter(self):
        """Test executing query without filter."""
        executor = QueryExecutor()
        entities = [
            {'PartitionKey': 'P1', 'RowKey': 'R1', 'Value': 1},
            {'PartitionKey': 'P1', 'RowKey': 'R2', 'Value': 2}
        ]
        
        options = ODataQueryOptions()
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 2
        assert result.query_stats.entities_scanned == 2
    
    def test_execute_with_filter(self):
        """Test executing query with filter."""
        executor = QueryExecutor()
        entities = [
            {'PartitionKey': 'P1', 'RowKey': 'R1', 'Value': 10},
            {'PartitionKey': 'P1', 'RowKey': 'R2', 'Value': 20},
            {'PartitionKey': 'P1', 'RowKey': 'R3', 'Value': 30}
        ]
        
        options = ODataQueryOptions(filter="Value gt 15")
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 2
        assert result.entities[0]['Value'] == 20
        assert result.entities[1]['Value'] == 30
    
    def test_execute_with_top(self):
        """Test executing query with $top."""
        executor = QueryExecutor()
        entities = [{'RowKey': f'R{i}', 'Value': i} for i in range(10)]
        
        options = ODataQueryOptions(top=5)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 5
    
    def test_execute_with_skip(self):
        """Test executing query with $skip."""
        executor = QueryExecutor()
        entities = [{'RowKey': f'R{i}', 'Value': i} for i in range(10)]
        
        options = ODataQueryOptions(skip=5)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 5
        assert result.entities[0]['Value'] == 5
    
    def test_execute_with_skip_and_top(self):
        """Test pagination with $skip and $top."""
        executor = QueryExecutor()
        entities = [{'RowKey': f'R{i}', 'Value': i} for i in range(100)]
        
        # Get page 2 (items 10-19)
        options = ODataQueryOptions(skip=10, top=10)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 10
        assert result.entities[0]['Value'] == 10
        assert result.entities[-1]['Value'] == 19
    
    def test_execute_with_orderby_asc(self):
        """Test sorting with $orderby ascending."""
        executor = QueryExecutor()
        entities = [
            {'RowKey': 'R1', 'Price': 30.0},
            {'RowKey': 'R2', 'Price': 10.0},
            {'RowKey': 'R3', 'Price': 20.0}
        ]
        
        options = ODataQueryOptions(
            orderby=[('Price', SortDirection.ASC)]
        )
        result = executor.execute(entities, options)
        
        assert result.entities[0]['Price'] == 10.0
        assert result.entities[1]['Price'] == 20.0
        assert result.entities[2]['Price'] == 30.0
    
    def test_execute_with_orderby_desc(self):
        """Test sorting with $orderby descending."""
        executor = QueryExecutor()
        entities = [
            {'RowKey': 'R1', 'Price': 10.0},
            {'RowKey': 'R2', 'Price': 30.0},
            {'RowKey': 'R3', 'Price': 20.0}
        ]
        
        options = ODataQueryOptions(
            orderby=[('Price', SortDirection.DESC)]
        )
        result = executor.execute(entities, options)
        
        assert result.entities[0]['Price'] == 30.0
        assert result.entities[1]['Price'] == 20.0
        assert result.entities[2]['Price'] == 10.0
    
    def test_execute_with_multi_column_sort(self):
        """Test sorting with multiple columns."""
        executor = QueryExecutor()
        entities = [
            {'Category': 'A', 'Price': 20.0},
            {'Category': 'B', 'Price': 10.0},
            {'Category': 'A', 'Price': 10.0},
            {'Category': 'B', 'Price': 20.0}
        ]
        
        options = ODataQueryOptions(
            orderby=[
                ('Category', SortDirection.ASC),
                ('Price', SortDirection.DESC)
            ]
        )
        result = executor.execute(entities, options)
        
        # Should be: A-20, A-10, B-20, B-10
        assert result.entities[0]['Category'] == 'A'
        assert result.entities[0]['Price'] == 20.0
        assert result.entities[1]['Category'] == 'A'
        assert result.entities[1]['Price'] == 10.0
    
    def test_execute_with_select(self):
        """Test projection with $select."""
        executor = QueryExecutor()
        entities = [
            {
                'PartitionKey': 'P1',
                'RowKey': 'R1',
                'Name': 'Item1',
                'Price': 10.0,
                'Stock': 100
            }
        ]
        
        options = ODataQueryOptions(select=['Name', 'Price'])
        result = executor.execute(entities, options)
        
        entity = result.entities[0]
        assert 'Name' in entity
        assert 'Price' in entity
        assert 'Stock' not in entity
        # System properties should be included
        assert 'PartitionKey' in entity
        assert 'RowKey' in entity
    
    def test_execute_count_only(self):
        """Test $count without entities."""
        executor = QueryExecutor()
        entities = [{'Value': i} for i in range(50)]
        
        options = ODataQueryOptions(
            filter="Value gt 25",
            count=True
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 0
        assert result.count == 24  # 26-49 = 24 entities
    
    def test_execute_with_inlinecount(self):
        """Test $inlinecount with entities."""
        executor = QueryExecutor()
        entities = [{'Value': i} for i in range(100)]
        
        options = ODataQueryOptions(
            filter="Value gt 50",
            top=10,
            inlinecount=True
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 10
        assert result.count == 49  # 51-99 = 49 entities
    
    def test_execute_with_continuation(self):
        """Test continuation token generation."""
        executor = QueryExecutor()
        entities = [
            {'PartitionKey': 'P1', 'RowKey': f'R{i:03d}', 'Value': i}
            for i in range(50)
        ]
        
        options = ODataQueryOptions(top=10)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 10
        assert result.continuation is not None
        assert result.continuation.partition_key == 'P1'
        assert result.continuation.skip_count == 10
    
    def test_execute_with_metadata(self):
        """Test metadata generation."""
        executor = QueryExecutor()
        entities = [
            {
                'PartitionKey': 'P1',
                'RowKey': 'R1',
                'Name': 'Test',
                'Price': 10.5,
                'Active': True,
                'Count': 100
            }
        ]
        
        options = ODataQueryOptions(metadata=True)
        result = executor.execute(entities, options)
        
        assert result.metadata is not None
        assert 'properties' in result.metadata
        
        props = result.metadata['properties']
        assert props['Name']['type'] == 'Edm.String'
        assert props['Price']['type'] == 'Edm.Double'
        assert props['Active']['type'] == 'Edm.Boolean'
        assert props['Count']['type'] == 'Edm.Int32'


class TestParseOrderby:
    """Tests for $orderby parsing."""
    
    def test_parse_single_ascending(self):
        """Test parsing single ascending sort."""
        result = parse_orderby("Name asc")
        
        assert len(result) == 1
        assert result[0] == ('Name', SortDirection.ASC)
    
    def test_parse_single_descending(self):
        """Test parsing single descending sort."""
        result = parse_orderby("Price desc")
        
        assert len(result) == 1
        assert result[0] == ('Price', SortDirection.DESC)
    
    def test_parse_default_ascending(self):
        """Test parsing without explicit direction."""
        result = parse_orderby("Name")
        
        assert len(result) == 1
        assert result[0] == ('Name', SortDirection.ASC)
    
    def test_parse_multiple_columns(self):
        """Test parsing multiple sort columns."""
        result = parse_orderby("Category asc, Price desc, Name")
        
        assert len(result) == 3
        assert result[0] == ('Category', SortDirection.ASC)
        assert result[1] == ('Price', SortDirection.DESC)
        assert result[2] == ('Name', SortDirection.ASC)


class TestParseQueryOptions:
    """Tests for query option parsing."""
    
    def test_parse_filter(self):
        """Test parsing $filter."""
        params = {'$filter': 'Price gt 50'}
        options = parse_query_options(params)
        
        assert options.filter == 'Price gt 50'
    
    def test_parse_select(self):
        """Test parsing $select."""
        params = {'$select': 'Name,Price,Stock'}
        options = parse_query_options(params)
        
        assert options.select == ['Name', 'Price', 'Stock']
    
    def test_parse_orderby(self):
        """Test parsing $orderby."""
        params = {'$orderby': 'Price desc, Name asc'}
        options = parse_query_options(params)
        
        assert len(options.orderby) == 2
        assert options.orderby[0] == ('Price', SortDirection.DESC)
        assert options.orderby[1] == ('Name', SortDirection.ASC)
    
    def test_parse_top(self):
        """Test parsing $top."""
        params = {'$top': '10'}
        options = parse_query_options(params)
        
        assert options.top == 10
    
    def test_parse_skip(self):
        """Test parsing $skip."""
        params = {'$skip': '20'}
        options = parse_query_options(params)
        
        assert options.skip == 20
    
    def test_parse_count(self):
        """Test parsing $count."""
        params = {'$count': 'true'}
        options = parse_query_options(params)
        
        assert options.count is True
    
    def test_parse_inlinecount(self):
        """Test parsing $inlinecount."""
        params = {'$inlinecount': 'allpages'}
        options = parse_query_options(params)
        
        assert options.inlinecount is True
    
    def test_parse_format(self):
        """Test parsing $format."""
        params = {'$format': 'atom'}
        options = parse_query_options(params)
        
        assert options.format == ResponseFormat.ATOM
    
    def test_parse_all_options(self):
        """Test parsing all options together."""
        params = {
            '$filter': 'Price gt 50',
            '$select': 'Name,Price',
            '$orderby': 'Price desc',
            '$top': '10',
            '$skip': '5',
            '$inlinecount': 'allpages'
        }
        
        options = parse_query_options(params)
        
        assert options.filter == 'Price gt 50'
        assert options.select == ['Name', 'Price']
        assert len(options.orderby) == 1
        assert options.top == 10
        assert options.skip == 5
        assert options.inlinecount is True


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_entity_list(self):
        """Test with empty entity list."""
        executor = QueryExecutor()
        options = ODataQueryOptions()
        
        result = executor.execute([], options)
        
        assert len(result.entities) == 0
        assert result.query_stats.entities_scanned == 0
    
    def test_sort_with_null_values(self):
        """Test sorting with null values."""
        executor = QueryExecutor()
        entities = [
            {'RowKey': 'R1', 'Price': 10.0},
            {'RowKey': 'R2', 'Price': None},
            {'RowKey': 'R3', 'Price': 20.0}
        ]
        
        options = ODataQueryOptions(
            orderby=[('Price', SortDirection.ASC)]
        )
        result = executor.execute(entities, options)
        
        # Nulls should sort to end
        assert result.entities[0]['Price'] == 10.0
        assert result.entities[1]['Price'] == 20.0
        assert result.entities[2]['Price'] is None
    
    def test_skip_beyond_results(self):
        """Test $skip beyond result count."""
        executor = QueryExecutor()
        entities = [{'Value': i} for i in range(10)]
        
        options = ODataQueryOptions(skip=20)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 0
    
    def test_top_larger_than_results(self):
        """Test $top larger than result count."""
        executor = QueryExecutor()
        entities = [{'Value': i} for i in range(5)]
        
        options = ODataQueryOptions(top=10)
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 5
        assert result.continuation is None


class TestIntegration:
    """Integration tests combining multiple features."""
    
    def test_filter_sort_page(self):
        """Test combined filter, sort, and pagination."""
        executor = QueryExecutor()
        entities = [
            {'RowKey': f'R{i}', 'Category': 'A' if i % 2 == 0 else 'B', 'Value': i}
            for i in range(50)
        ]
        
        options = ODataQueryOptions(
            filter="Category eq 'A'",
            orderby=[('Value', SortDirection.DESC)],
            skip=5,
            top=10
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 10
        # Should be values: 38, 36, 34, ... (descending evens, skipping first 5)
        assert all(e['Category'] == 'A' for e in result.entities)
        assert result.entities[0]['Value'] > result.entities[1]['Value']
    
    def test_select_count_metadata(self):
        """Test combined projection, count, and metadata."""
        executor = QueryExecutor()
        entities = [
            {'PartitionKey': 'P1', 'RowKey': f'R{i}', 'Name': f'Item{i}', 'Price': i * 10.0}
            for i in range(20)
        ]
        
        options = ODataQueryOptions(
            select=['Name'],
            inlinecount=True,
            metadata=True,
            top=5
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 5
        assert result.count == 20
        assert result.metadata is not None
        # Should only have Name (plus system props)
        assert 'Name' in result.entities[0]
        assert 'Price' not in result.entities[0]


class TestComplexScenarios:
    """Tests for complex real-world scenarios."""
    
    def test_large_dataset_pagination(self):
        """Test pagination with large dataset."""
        executor = QueryExecutor()
        entities = [
            {'PartitionKey': f'P{i//100}', 'RowKey': f'R{i:04d}', 'Value': i}
            for i in range(1000)
        ]
        
        # Page through results
        all_values = []
        skip = 0
        page_size = 50
        
        while True:
            options = ODataQueryOptions(skip=skip, top=page_size)
            result = executor.execute(entities, options)
            
            if not result.entities:
                break
            
            all_values.extend([e['Value'] for e in result.entities])
            skip += page_size
            
            if len(result.entities) < page_size:
                break
        
        assert len(all_values) == 1000
        assert all_values == list(range(1000))
    
    def test_complex_multi_sort(self):
        """Test complex multi-column sorting."""
        executor = QueryExecutor()
        entities = [
            {'Region': 'US', 'State': 'CA', 'City': 'SF', 'Pop': 800000},
            {'Region': 'US', 'State': 'NY', 'City': 'NYC', 'Pop': 8000000},
            {'Region': 'US', 'State': 'CA', 'City': 'LA', 'Pop': 4000000},
            {'Region': 'EU', 'State': 'UK', 'City': 'London', 'Pop': 9000000},
            {'Region': 'EU', 'State': 'FR', 'City': 'Paris', 'Pop': 2000000},
        ]
        
        options = ODataQueryOptions(
            orderby=[
                ('Region', SortDirection.ASC),
                ('State', SortDirection.ASC),
                ('Pop', SortDirection.DESC)
            ]
        )
        result = executor.execute(entities, options)
        
        # EU-FR-Paris, EU-UK-London, US-CA-LA, US-CA-SF, US-NY-NYC
        assert result.entities[0]['City'] == 'Paris'
        assert result.entities[1]['City'] == 'London'
        assert result.entities[2]['City'] == 'LA'  # CA, larger pop
        assert result.entities[3]['City'] == 'SF'   # CA, smaller pop
    
    def test_filter_with_complex_expressions(self):
        """Test filtering with complex expressions."""
        executor = QueryExecutor()
        entities = [
            {'Name': 'Item1', 'Price': 10, 'Stock': 100, 'Active': True},
            {'Name': 'Item2', 'Price': 20, 'Stock': 50, 'Active': True},
            {'Name': 'Item3', 'Price': 30, 'Stock': 200, 'Active': False},
            {'Name': 'Item4', 'Price': 15, 'Stock': 75, 'Active': True},
        ]
        
        options = ODataQueryOptions(
            filter="(Price gt 10 and Price lt 25) and Active eq true"
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 2
        assert result.entities[0]['Name'] == 'Item2'
        assert result.entities[1]['Name'] == 'Item4'
    
    def test_string_sorting(self):
        """Test sorting with string values."""
        executor = QueryExecutor()
        entities = [
            {'Name': 'Zebra', 'Value': 1},
            {'Name': 'Apple', 'Value': 2},
            {'Name': 'Mango', 'Value': 3},
            {'Name': 'Banana', 'Value': 4}
        ]
        
        options = ODataQueryOptions(
            orderby=[('Name', SortDirection.ASC)]
        )
        result = executor.execute(entities, options)
        
        names = [e['Name'] for e in result.entities]
        assert names == ['Apple', 'Banana', 'Mango', 'Zebra']
    
    def test_mixed_type_properties(self):
        """Test with mixed property types."""
        executor = QueryExecutor()
        from datetime import datetime
        
        entities = [
            {
                'PartitionKey': 'P1',
                'RowKey': 'R1',
                'Timestamp': datetime(2025, 1, 1),
                'Name': 'Item1',
                'Price': 10.5,
                'Count': 100,
                'Active': True
            }
        ]
        
        options = ODataQueryOptions(metadata=True)
        result = executor.execute(entities, options)
        
        assert result.metadata is not None
        props = result.metadata['properties']
        assert props['Name']['type'] == 'Edm.String'
        assert props['Price']['type'] == 'Edm.Double'
        assert props['Count']['type'] == 'Edm.Int32'
        assert props['Active']['type'] == 'Edm.Boolean'
        assert props['Timestamp']['type'] == 'Edm.DateTime'
    
    def test_empty_select_list(self):
        """Test with empty select list."""
        executor = QueryExecutor()
        entities = [{'PartitionKey': 'P1', 'RowKey': 'R1', 'Name': 'Test', 'Value': 1}]
        
        options = ODataQueryOptions(select=[])
        result = executor.execute(entities, options)
        
        # With empty select, only system properties should be included
        # But current implementation still returns properties if they're in select list
        # Since select is empty, should have system props
        assert 'PartitionKey' in result.entities[0]
        assert 'RowKey' in result.entities[0]
    
    def test_continuation_token_validation(self):
        """Test continuation token includes query hash."""
        executor = QueryExecutor()
        entities = [{'PartitionKey': 'P1', 'RowKey': f'R{i}', 'Value': i} for i in range(20)]
        
        options = ODataQueryOptions(
            filter="Value gt 5",
            top=5
        )
        result = executor.execute(entities, options)
        
        assert result.continuation is not None
        assert result.continuation.query_hash == options.get_hash()
    
    def test_query_statistics_accuracy(self):
        """Test query statistics are accurate."""
        executor = QueryExecutor()
        entities = [{'Value': i} for i in range(100)]
        
        options = ODataQueryOptions(
            filter="Value gt 50",
            top=10
        )
        result = executor.execute(entities, options)
        
        assert result.query_stats.entities_scanned == 100
        assert result.query_stats.entities_returned == 10
        assert result.query_stats.entities_filtered == 51  # 0-50 filtered out
        assert result.query_stats.execution_time_ms > 0
    
    def test_orderby_with_skip_top(self):
        """Test sorting combined with pagination."""
        executor = QueryExecutor()
        entities = [
            {'Name': f'Item{i:02d}', 'Score': 100 - i}
            for i in range(50)
        ]
        
        # Get items 10-19 sorted by score descending
        options = ODataQueryOptions(
            orderby=[('Score', SortDirection.DESC)],
            skip=10,
            top=10
        )
        result = executor.execute(entities, options)
        
        assert len(result.entities) == 10
        # First should be 11th highest score (90)
        assert result.entities[0]['Score'] == 90
        assert result.entities[-1]['Score'] == 81


class TestPerformance:
    """Performance-related tests."""
    
    def test_sort_performance_large_dataset(self):
        """Test sorting performance with large dataset."""
        executor = QueryExecutor()
        entities = [
            {'RowKey': f'R{i}', 'Value': i}
            for i in range(1, 1001)
        ]
        
        options = ODataQueryOptions(
            orderby=[('Value', SortDirection.ASC)]
        )
        result = executor.execute(entities, options)
        
        # Should complete and be sorted
        assert len(result.entities) == 1000
        assert result.entities[0]['Value'] == 1
        assert result.entities[-1]['Value'] == 1000
    
    def test_filter_performance_large_dataset(self):
        """Test filtering performance with large dataset."""
        executor = QueryExecutor()
        entities = [{'Value': i, 'Category': 'A' if i % 2 == 0 else 'B'} for i in range(10000)]
        
        options = ODataQueryOptions(
            filter="Category eq 'A' and Value gt 5000"
        )
        result = executor.execute(entities, options)
        
        # Should complete and have correct results
        # Even numbers from 5002 to 9998: (9998-5002)/2 + 1 = 2499
        assert len(result.entities) == 2499
