"""
Advanced OData Query Features for Table Storage.

This module provides comprehensive OData query options support including:
- $orderby: Sorting with multiple keys and directions
- $skip: Result pagination offset
- $count: Return only result count
- $inlinecount: Include count with results
- $format: Response format (json, atom)
- $metadata: Include type metadata
- Server-side paging: Automatic continuation tokens

Features:
- Multi-column sorting (asc/desc)
- Efficient pagination with continuation tokens
- Metadata inclusion for type information
- Format negotiation
- Query statistics and metrics

Example:
    >>> from localzure.services.table.advanced import ODataQueryOptions, QueryResultSet
    >>> 
    >>> options = ODataQueryOptions(
    ...     filter="Price gt 50",
    ...     select=["Name", "Price"],
    ...     orderby=[("Price", SortDirection.DESC)],
    ...     top=10,
    ...     skip=20,
    ...     count=False,
    ...     inlinecount=True
    ... )
    >>> 
    >>> results = execute_query(entities, options)
    >>> print(f"Count: {results.count}, Entities: {len(results.entities)}")

Author: LocalZure Team
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib
import base64


class SortDirection(Enum):
    """Sort direction for $orderby."""
    ASC = "asc"
    DESC = "desc"
    
    def __str__(self) -> str:
        return self.value


class ResponseFormat(Enum):
    """Response format for $format."""
    JSON = "json"
    ATOM = "atom"
    
    def __str__(self) -> str:
        return self.value


@dataclass
class ContinuationToken:
    """
    Continuation token for server-side paging.
    
    Encodes the position in the result set to resume from.
    
    Attributes:
        partition_key: Last partition key
        row_key: Last row key
        skip_count: Number of results already returned
        total_scanned: Total entities scanned
        query_hash: Hash of query options for validation
    """
    partition_key: str
    row_key: str
    skip_count: int = 0
    total_scanned: int = 0
    query_hash: str = ""
    
    def encode(self) -> str:
        """
        Encode continuation token to base64 string.
        
        Returns:
            Base64 encoded token string
        """
        token_str = f"{self.partition_key}|{self.row_key}|{self.skip_count}|{self.total_scanned}|{self.query_hash}"
        return base64.b64encode(token_str.encode()).decode()
    
    @staticmethod
    def decode(token_str: str) -> 'ContinuationToken':
        """
        Decode continuation token from base64 string.
        
        Args:
            token_str: Base64 encoded token
            
        Returns:
            Decoded continuation token
            
        Raises:
            ValueError: If token is invalid
        """
        try:
            decoded = base64.b64decode(token_str.encode()).decode()
            parts = decoded.split('|')
            
            if len(parts) != 5:
                raise ValueError("Invalid continuation token format")
            
            return ContinuationToken(
                partition_key=parts[0],
                row_key=parts[1],
                skip_count=int(parts[2]),
                total_scanned=int(parts[3]),
                query_hash=parts[4]
            )
        except Exception as e:
            raise ValueError(f"Failed to decode continuation token: {e}")


@dataclass
class QueryStatistics:
    """
    Query execution statistics.
    
    Attributes:
        entities_scanned: Total entities scanned
        entities_returned: Entities in result set
        entities_filtered: Entities filtered out
        execution_time_ms: Query execution time
        sort_time_ms: Sorting time (if applicable)
        cache_hit: Whether query plan was cached
    """
    entities_scanned: int = 0
    entities_returned: int = 0
    entities_filtered: int = 0
    execution_time_ms: float = 0.0
    sort_time_ms: float = 0.0
    cache_hit: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entities_scanned': self.entities_scanned,
            'entities_returned': self.entities_returned,
            'entities_filtered': self.entities_filtered,
            'execution_time_ms': round(self.execution_time_ms, 2),
            'sort_time_ms': round(self.sort_time_ms, 2),
            'cache_hit': self.cache_hit
        }


@dataclass
class ODataQueryOptions:
    """
    Complete OData query options for Table Storage.
    
    Supports all major OData query parameters for filtering, projection,
    sorting, pagination, and metadata.
    
    Attributes:
        filter: $filter expression string
        select: $select property list
        orderby: $orderby list of (property, direction) tuples
        top: $top result limit
        skip: $skip result offset
        count: $count - return only count
        inlinecount: $inlinecount - include count with results
        expand: $expand related entities (reserved for future)
        format: $format response format
        metadata: Include type metadata
        continuation: Continuation token for paging
    """
    filter: Optional[str] = None
    select: Optional[List[str]] = None
    orderby: Optional[List[Tuple[str, SortDirection]]] = None
    top: Optional[int] = None
    skip: Optional[int] = None
    count: bool = False
    inlinecount: bool = False
    expand: Optional[List[str]] = None
    format: ResponseFormat = ResponseFormat.JSON
    metadata: bool = False
    continuation: Optional[ContinuationToken] = None
    
    def __post_init__(self):
        """Validate query options."""
        if self.top is not None and self.top < 0:
            raise ValueError("$top must be non-negative")
        
        if self.skip is not None and self.skip < 0:
            raise ValueError("$skip must be non-negative")
        
        if self.top is not None and self.top > 1000:
            # Azure Table Storage limit
            self.top = 1000
    
    def get_hash(self) -> str:
        """
        Get hash of query options for caching and validation.
        
        Returns:
            Hash string
        """
        # Create stable string representation
        parts = [
            f"filter={self.filter or ''}",
            f"select={','.join(self.select) if self.select else ''}",
            f"orderby={','.join(f'{p}:{d}' for p, d in self.orderby) if self.orderby else ''}",
            f"top={self.top or ''}",
            f"skip={self.skip or ''}",
        ]
        
        query_str = '|'.join(parts)
        return hashlib.sha256(query_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {}
        
        if self.filter:
            result['$filter'] = self.filter
        if self.select:
            result['$select'] = ','.join(self.select)
        if self.orderby:
            result['$orderby'] = ','.join(
                f"{prop} {dir.value}" for prop, dir in self.orderby
            )
        if self.top is not None:
            result['$top'] = self.top
        if self.skip is not None:
            result['$skip'] = self.skip
        if self.count:
            result['$count'] = True
        if self.inlinecount:
            result['$inlinecount'] = 'allpages'
        if self.format != ResponseFormat.JSON:
            result['$format'] = self.format.value
        
        return result


@dataclass
class QueryResultSet:
    """
    Query result set with entities and metadata.
    
    Encapsulates query results with pagination, counts, and statistics.
    
    Attributes:
        entities: List of matching entities
        count: Total count of matching entities (if requested)
        continuation: Continuation token for next page
        query_stats: Execution statistics
        metadata: Type metadata (if requested)
    """
    entities: List[Dict[str, Any]]
    count: Optional[int] = None
    continuation: Optional[ContinuationToken] = None
    query_stats: QueryStatistics = field(default_factory=QueryStatistics)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self, include_stats: bool = False) -> Dict[str, Any]:
        """
        Convert result set to dictionary.
        
        Args:
            include_stats: Include query statistics
            
        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {
            'value': self.entities
        }
        
        if self.count is not None:
            result['odata.count'] = self.count
        
        if self.continuation:
            result['x-ms-continuation-token'] = self.continuation.encode()
        
        if include_stats:
            result['query_stats'] = self.query_stats.to_dict()
        
        if self.metadata:
            result['odata.metadata'] = self.metadata
        
        return result


class QueryExecutor:
    """
    Advanced query executor with sorting, pagination, and metadata.
    
    Executes OData queries with full feature support including ordering,
    pagination, and count operations.
    
    Thread Safety:
        QueryExecutor instances are thread-safe for read operations.
    """
    
    def __init__(self):
        """Initialize query executor."""
        self._query_cache: Dict[str, Any] = {}
    
    def execute(
        self,
        entities: List[Dict[str, Any]],
        options: ODataQueryOptions,
        from_evaluator: Optional[Any] = None
    ) -> QueryResultSet:
        """
        Execute query with all options.
        
        Args:
            entities: List of entities to query
            options: Query options
            from_evaluator: Optional pre-filtered evaluator result
            
        Returns:
            Query result set with entities and metadata
        """
        import time
        start_time = time.perf_counter()
        
        stats = QueryStatistics()
        stats.entities_scanned = len(entities)
        
        # Handle count-only query
        if options.count and not options.inlinecount:
            # For count-only, we still need to filter but don't return entities
            if options.filter:
                from localzure.services.table.lexer import ODataLexer
                from localzure.services.table.parser import ODataParser
                from localzure.services.table.evaluator import QueryEvaluator
                
                lexer = ODataLexer(options.filter)
                tokens = lexer.tokenize()
                parser = ODataParser(tokens)
                ast = parser.parse()
                evaluator = QueryEvaluator()
                
                filtered = [e for e in entities if evaluator.evaluate(ast, e)]
            else:
                filtered = entities
            
            stats.entities_returned = 0
            stats.entities_filtered = len(entities) - len(filtered)
            stats.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            return QueryResultSet(
                entities=[],
                count=len(filtered),
                query_stats=stats
            )
        
        # Apply filter
        if options.filter:
            from localzure.services.table.lexer import ODataLexer
            from localzure.services.table.parser import ODataParser
            from localzure.services.table.evaluator import QueryEvaluator
            
            lexer = ODataLexer(options.filter)
            tokens = lexer.tokenize()
            parser = ODataParser(tokens)
            ast = parser.parse()
            evaluator = QueryEvaluator()
            
            filtered = [e for e in entities if evaluator.evaluate(ast, e)]
        else:
            filtered = list(entities)
        
        stats.entities_filtered = len(entities) - len(filtered)
        
        # Store total count if needed
        total_count = len(filtered) if options.inlinecount else None
        
        # Apply sorting
        if options.orderby:
            sort_start = time.perf_counter()
            filtered = self._sort_entities(filtered, options.orderby)
            stats.sort_time_ms = (time.perf_counter() - sort_start) * 1000
        
        # Apply skip
        if options.skip:
            filtered = filtered[options.skip:]
        
        # Apply top
        if options.top:
            filtered = filtered[:options.top]
        
        # Apply projection
        if options.select:
            filtered = [self._project_entity(e, options.select) for e in filtered]
        
        # Create continuation token if needed
        continuation = None
        if options.top and len(filtered) == options.top:
            # More results might exist
            last_entity = filtered[-1]
            continuation = ContinuationToken(
                partition_key=last_entity.get('PartitionKey', ''),
                row_key=last_entity.get('RowKey', ''),
                skip_count=(options.skip or 0) + len(filtered),
                total_scanned=stats.entities_scanned,
                query_hash=options.get_hash()
            )
        
        stats.entities_returned = len(filtered)
        stats.execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Build metadata if requested
        metadata = None
        if options.metadata:
            metadata = self._build_metadata(filtered)
        
        return QueryResultSet(
            entities=filtered,
            count=total_count,
            continuation=continuation,
            query_stats=stats,
            metadata=metadata
        )
    
    def _sort_entities(
        self,
        entities: List[Dict[str, Any]],
        orderby: List[Tuple[str, SortDirection]]
    ) -> List[Dict[str, Any]]:
        """
        Sort entities by multiple keys.
        
        Args:
            entities: Entities to sort
            orderby: List of (property, direction) tuples
            
        Returns:
            Sorted entity list
        """
        def get_sort_key(entity: Dict[str, Any]) -> Tuple:
            """Extract sort key tuple from entity."""
            keys = []
            for prop, direction in orderby:
                value = entity.get(prop)
                
                # Handle None values (sort to end)
                # Use tuple to ensure None sorts after all values
                if value is None:
                    if direction == SortDirection.ASC:
                        # For ascending, use (1, 0) which sorts after (0, any_value)
                        keys.append((1, 0))
                    else:
                        # For descending, use (1, 0) which still sorts after real values
                        keys.append((1, 0))
                else:
                    # Real values get (0, value) tuple
                    # For descending, negate numbers or reverse strings
                    if direction == SortDirection.DESC:
                        if isinstance(value, (int, float)):
                            value = -value
                        elif isinstance(value, str):
                            # Create reverse-sortable string
                            value = ''.join(chr(255 - ord(c)) for c in value[:100])  # Limit length
                    
                    keys.append((0, value))
            
            return tuple(keys)
        
        try:
            return sorted(entities, key=get_sort_key)
        except Exception:
            # If sorting fails (e.g., incomparable types), return unsorted
            return entities
    
    def _project_entity(
        self,
        entity: Dict[str, Any],
        select: List[str]
    ) -> Dict[str, Any]:
        """
        Project entity to selected properties.
        
        Args:
            entity: Entity to project
            select: Property names to include
            
        Returns:
            Projected entity
        """
        # Always include system properties
        system_props = {'PartitionKey', 'RowKey', 'Timestamp', 'odata.etag', 'etag'}
        
        result = {}
        for key, value in entity.items():
            if key in system_props or key in select:
                result[key] = value
        
        return result
    
    def _build_metadata(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build type metadata for entities.
        
        Args:
            entities: Entity list
            
        Returns:
            Metadata dictionary
        """
        if not entities:
            return {'properties': {}}
        
        # Infer types from first entity
        sample = entities[0]
        properties = {}
        
        for key, value in sample.items():
            if key in {'PartitionKey', 'RowKey'}:
                properties[key] = {'type': 'Edm.String'}
            elif key == 'Timestamp':
                properties[key] = {'type': 'Edm.DateTime'}
            elif isinstance(value, bool):
                properties[key] = {'type': 'Edm.Boolean'}
            elif isinstance(value, int):
                properties[key] = {'type': 'Edm.Int32'}
            elif isinstance(value, float):
                properties[key] = {'type': 'Edm.Double'}
            elif isinstance(value, str):
                properties[key] = {'type': 'Edm.String'}
            elif isinstance(value, datetime):
                properties[key] = {'type': 'Edm.DateTime'}
            else:
                properties[key] = {'type': 'Edm.Binary'}
        
        return {'properties': properties}


def parse_orderby(orderby_str: str) -> List[Tuple[str, SortDirection]]:
    """
    Parse $orderby query parameter.
    
    Format: "prop1 asc, prop2 desc, prop3"
    
    Args:
        orderby_str: $orderby parameter value
        
    Returns:
        List of (property, direction) tuples
        
    Example:
        >>> parse_orderby("Price desc, Name asc")
        [('Price', SortDirection.DESC), ('Name', SortDirection.ASC)]
    """
    result = []
    
    for part in orderby_str.split(','):
        part = part.strip()
        
        if ' ' in part:
            prop, direction = part.rsplit(' ', 1)
            prop = prop.strip()
            direction = direction.strip().lower()
            
            if direction == 'desc':
                result.append((prop, SortDirection.DESC))
            else:
                result.append((prop, SortDirection.ASC))
        else:
            # Default to ascending
            result.append((part, SortDirection.ASC))
    
    return result


def parse_query_options(query_params: Dict[str, str]) -> ODataQueryOptions:
    """
    Parse query parameters into ODataQueryOptions.
    
    Args:
        query_params: Dictionary of query parameters
        
    Returns:
        Parsed query options
        
    Example:
        >>> params = {
        ...     '$filter': 'Price gt 50',
        ...     '$orderby': 'Name asc',
        ...     '$top': '10'
        ... }
        >>> options = parse_query_options(params)
    """
    options = ODataQueryOptions()
    
    if '$filter' in query_params:
        options.filter = query_params['$filter']
    
    if '$select' in query_params:
        options.select = [p.strip() for p in query_params['$select'].split(',')]
    
    if '$orderby' in query_params:
        options.orderby = parse_orderby(query_params['$orderby'])
    
    if '$top' in query_params:
        try:
            options.top = int(query_params['$top'])
        except ValueError:
            pass
    
    if '$skip' in query_params:
        try:
            options.skip = int(query_params['$skip'])
        except ValueError:
            pass
    
    if '$count' in query_params:
        options.count = query_params['$count'].lower() in ('true', '1')
    
    if '$inlinecount' in query_params:
        options.inlinecount = query_params['$inlinecount'].lower() == 'allpages'
    
    if '$format' in query_params:
        format_val = query_params['$format'].lower()
        if format_val == 'atom':
            options.format = ResponseFormat.ATOM
    
    return options
