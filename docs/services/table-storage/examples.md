# OData Query Examples Library

## Table of Contents

1. [Basic Comparisons](#basic-comparisons)
2. [Logical Operations](#logical-operations)
3. [String Functions](#string-functions)
4. [Arithmetic Operations](#arithmetic-operations)
5. [Date Functions](#date-functions)
6. [Complex Queries](#complex-queries)
7. [Sorting and Pagination](#sorting-and-pagination)
8. [Projection and Counting](#projection-and-counting)
9. [Real-World Scenarios](#real-world-scenarios)
10. [Performance Patterns](#performance-patterns)

---

## Basic Comparisons

### Equal (eq)

```python
# Single property equality
filter_expr = "Name eq 'Alice'"

# Numeric equality
filter_expr = "Age eq 30"

# Boolean equality
filter_expr = "Active eq true"

# Null check
filter_expr = "Description eq null"
```

### Not Equal (ne)

```python
# String not equal
filter_expr = "Status ne 'Deleted'"

# Numeric not equal
filter_expr = "Quantity ne 0"

# Null check
filter_expr = "Name ne null"
```

### Greater Than (gt)

```python
# Numeric greater than
filter_expr = "Price gt 100"

# Date greater than
filter_expr = "CreatedAt gt datetime'2024-01-01T00:00:00'"
```

### Greater Than or Equal (ge)

```python
filter_expr = "Age ge 18"
filter_expr = "Rating ge 4.5"
```

### Less Than (lt)

```python
filter_expr = "Price lt 50"
filter_expr = "Stock lt 10"
```

### Less Than or Equal (le)

```python
filter_expr = "Discount le 0.5"
filter_expr = "Temperature le 100"
```

---

## Logical Operations

### AND

```python
# Two conditions
filter_expr = "Price gt 10 and Price lt 100"

# Multiple conditions
filter_expr = "Active eq true and Stock gt 0 and Price lt 100"

# With parentheses
filter_expr = "(Category eq 'Electronics') and (Price gt 100)"
```

### OR

```python
# Two alternatives
filter_expr = "Category eq 'Books' or Category eq 'Movies'"

# Multiple alternatives
filter_expr = "Status eq 'Active' or Status eq 'Pending' or Status eq 'InProgress'"

# With parentheses
filter_expr = "(Price lt 10) or (OnSale eq true)"
```

### NOT

```python
# Negate single condition
filter_expr = "not (Status eq 'Deleted')"

# Negate complex expression
filter_expr = "not ((Price gt 100) and (Stock eq 0))"

# Multiple negations
filter_expr = "not (Category eq 'Archive') and not (Status eq 'Deleted')"
```

### Combined Logic

```python
# AND + OR
filter_expr = "(Price gt 10 and Price lt 100) or Category eq 'Sale'"

# OR + AND
filter_expr = "Category eq 'Books' or (Category eq 'Electronics' and Price lt 500)"

# Complex nested
filter_expr = "((Price gt 10 and Price lt 50) or (Price gt 100 and Price lt 200)) and Active eq true"

# NOT + AND + OR
filter_expr = "not (Status eq 'Deleted') and (Category eq 'Premium' or Rating ge 4)"
```

---

## String Functions

### substringof

```python
# Check if string contains substring
filter_expr = "substringof('micro', tolower(Company))"

# Case-sensitive contains
filter_expr = "substringof('Corp', Name)"

# Multiple substring checks
filter_expr = "substringof('john', tolower(FirstName)) or substringof('jane', tolower(FirstName))"
```

### startswith

```python
# Check prefix
filter_expr = "startswith(Name, 'Dr.')"

# Case-insensitive prefix
filter_expr = "startswith(tolower(Email), 'admin')"

# Combined with other conditions
filter_expr = "startswith(ProductCode, 'SKU-') and Active eq true"
```

### endswith

```python
# Check suffix
filter_expr = "endswith(Email, '@example.com')"

# Case-insensitive suffix
filter_expr = "endswith(tolower(Filename), '.pdf')"

# Domain check
filter_expr = "endswith(Email, '@company.com') or endswith(Email, '@company.net')"
```

### indexof

```python
# Find position
filter_expr = "indexof(Name, '@') gt 0"

# Not found check
filter_expr = "indexof(Description, 'deprecated') eq -1"

# Find in lowercase
filter_expr = "indexof(tolower(Title), 'urgent') ge 0"
```

### substring

```python
# Extract from position
filter_expr = "substring(ProductCode, 4) eq '12345'"

# Extract with length
filter_expr = "substring(Name, 0, 3) eq 'Dr.'"

# Extract area code
filter_expr = "substring(PhoneNumber, 0, 3) eq '555'"
```

### replace

```python
# Replace substring
filter_expr = "replace(Name, ' ', '') eq 'JohnDoe'"

# Remove characters
filter_expr = "replace(PhoneNumber, '-', '') eq '5551234567'"

# Normalize
filter_expr = "replace(tolower(Status), '_', ' ') eq 'in progress'"
```

### tolower / toupper

```python
# Case-insensitive comparison
filter_expr = "tolower(Name) eq 'alice'"

# Uppercase comparison
filter_expr = "toupper(Code) eq 'ABC123'"

# Combined
filter_expr = "tolower(Email) eq tolower('Admin@Example.com')"
```

### trim

```python
# Remove whitespace
filter_expr = "trim(Name) eq 'Alice'"

# Check non-empty after trim
filter_expr = "length(trim(Description)) gt 0"

# Normalized comparison
filter_expr = "trim(tolower(Status)) eq 'active'"
```

### concat

```python
# Concatenate fields
filter_expr = "concat(FirstName, LastName) eq 'JohnDoe'"

# With separator
filter_expr = "concat(concat(City, ', '), State) eq 'Seattle, WA'"

# Build identifier
filter_expr = "concat('SKU-', ProductId) eq 'SKU-12345'"
```

### length

```python
# Check string length
filter_expr = "length(Name) gt 5"

# Exact length
filter_expr = "length(Code) eq 10"

# Empty check
filter_expr = "length(Description) gt 0"

# Range check
filter_expr = "length(Password) ge 8 and length(Password) le 128"
```

---

## Arithmetic Operations

### Addition (add)

```python
# Add constants
filter_expr = "Price add 10 gt 100"

# Add properties
filter_expr = "BasePrice add Tax gt 100"

# Multiple additions
filter_expr = "Price add Shipping add Tax gt 200"
```

### Subtraction (sub)

```python
# Subtract constant
filter_expr = "Price sub Discount gt 50"

# Calculate difference
filter_expr = "MaxValue sub MinValue gt 100"

# Multiple subtractions
filter_expr = "Revenue sub Cost sub Tax gt 1000"
```

### Multiplication (mul)

```python
# Calculate total
filter_expr = "Price mul Quantity gt 1000"

# Percentage
filter_expr = "Price mul 1.2 gt 100"  # 20% markup

# Area calculation
filter_expr = "Width mul Height gt 100"
```

### Division (div)

```python
# Calculate average
filter_expr = "TotalScore div TestCount ge 85"

# Unit conversion
filter_expr = "PriceInCents div 100 gt 10"

# Ratio
filter_expr = "Revenue div Cost gt 1.5"
```

### Modulo (mod)

```python
# Even check
filter_expr = "OrderId mod 2 eq 0"

# Divisibility
filter_expr = "Amount mod 100 eq 0"

# Batch grouping
filter_expr = "RecordId mod 10 eq 5"
```

### Unary Minus

```python
# Negative value
filter_expr = "Balance lt -100"

# Negate property
filter_expr = "sub(0, Debt) gt 1000"  # -Debt > 1000
```

### Complex Arithmetic

```python
# Order of operations
filter_expr = "(Price mul Quantity) add Shipping gt 100"

# Multiple operations
filter_expr = "((Revenue sub Cost) div Revenue) gt 0.3"  # 30% profit margin

# With parentheses
filter_expr = "Price mul (1 add TaxRate) gt 100"
```

---

## Date Functions

### year

```python
# Current year
filter_expr = "year(CreatedAt) eq 2024"

# Year range
filter_expr = "year(OrderDate) ge 2020 and year(OrderDate) le 2024"

# Not this year
filter_expr = "year(ExpiryDate) ne 2024"
```

### month

```python
# Specific month
filter_expr = "month(OrderDate) eq 12"  # December

# Month range
filter_expr = "month(CreatedAt) ge 6 and month(CreatedAt) le 8"  # Summer

# Q1 check
filter_expr = "month(QuarterStart) ge 1 and month(QuarterStart) le 3"
```

### day

```python
# Specific day
filter_expr = "day(OrderDate) eq 15"

# First/last day of month
filter_expr = "day(CreatedAt) eq 1"
filter_expr = "day(CreatedAt) ge 28"

# Weekend check (requires additional logic in code)
filter_expr = "day(EventDate) ge 20"
```

### hour

```python
# Business hours
filter_expr = "hour(Timestamp) ge 9 and hour(Timestamp) lt 17"

# Night shift
filter_expr = "hour(CreatedAt) ge 22 or hour(CreatedAt) lt 6"

# Specific hour
filter_expr = "hour(ScheduledTime) eq 14"
```

### minute

```python
# Specific minute
filter_expr = "minute(Timestamp) eq 30"

# First half hour
filter_expr = "minute(EventTime) lt 30"

# Quarter hour marks
filter_expr = "minute(ScheduledTime) mod 15 eq 0"
```

### second

```python
# Specific second
filter_expr = "second(Timestamp) eq 0"

# Subsecond precision check
filter_expr = "second(EventTime) ge 30"
```

### Combined Date Functions

```python
# Specific date
filter_expr = "year(OrderDate) eq 2024 and month(OrderDate) eq 6 and day(OrderDate) eq 15"

# Date range (same year)
filter_expr = "year(CreatedAt) eq 2024 and month(CreatedAt) ge 6 and month(CreatedAt) le 12"

# Business hours + specific date
filter_expr = "year(Timestamp) eq 2024 and month(Timestamp) eq 12 and hour(Timestamp) ge 9 and hour(Timestamp) lt 17"

# Weekend filter (Saturday=6, Sunday=0 - needs custom logic)
filter_expr = "year(EventDate) eq 2024 and month(EventDate) eq 12"
```

---

## Complex Queries

### Nested Parentheses

```python
# Deep nesting
filter_expr = "((Price gt 10 and Price lt 50) or (Price gt 100 and Price lt 200)) and ((Category eq 'Sale') or (Rating ge 4))"

# Multiple levels
filter_expr = "(((Status eq 'Active') or (Status eq 'Pending')) and ((Priority eq 'High') or (Priority eq 'Critical')))"
```

### Multiple String Operations

```python
# Chained string functions
filter_expr = "substringof('admin', tolower(trim(Email)))"

# Multiple string checks
filter_expr = "startswith(Name, 'Dr.') and endswith(Email, '.edu')"

# Complex string filter
filter_expr = "length(trim(Description)) gt 100 and substringof('important', tolower(Description))"
```

### Mixed Type Queries

```python
# String + number + boolean
filter_expr = "Category eq 'Premium' and Price gt 100 and Active eq true"

# String + date + number
filter_expr = "Status eq 'Active' and year(CreatedAt) eq 2024 and Quantity gt 0"

# All types
filter_expr = "Name ne null and Price gt 0 and Active eq true and year(CreatedAt) eq 2024"
```

### Range Queries

```python
# Numeric range
filter_expr = "Price ge 10 and Price le 100"

# Date range
filter_expr = "CreatedAt ge datetime'2024-01-01T00:00:00' and CreatedAt lt datetime'2024-12-31T23:59:59'"

# Multiple ranges
filter_expr = "(Price ge 10 and Price le 50) or (Price ge 100 and Price le 200)"
```

### Exclusion Queries

```python
# Exclude values
filter_expr = "Status ne 'Deleted' and Status ne 'Archived'"

# Exclude range
filter_expr = "not (Price ge 50 and Price le 100)"

# Multiple exclusions
filter_expr = "Category ne 'Archive' and Status ne 'Deleted' and Active eq true"
```

---

## Sorting and Pagination

### Basic Sorting

```python
from localzure.services.table.advanced import parse_query_options

# Ascending (default)
query_params = {
    "$orderby": "Name"
}

# Explicit ascending
query_params = {
    "$orderby": "Name asc"
}

# Descending
query_params = {
    "$orderby": "Price desc"
}
```

### Multi-Column Sorting

```python
# Two columns
query_params = {
    "$orderby": "Category asc, Price desc"
}

# Three columns
query_params = {
    "$orderby": "Region asc, State asc, Population desc"
}

# Mixed directions
query_params = {
    "$orderby": "Priority desc, CreatedAt asc, Name asc"
}
```

### Pagination with $top

```python
# First 10 results
query_params = {
    "$filter": "Active eq true",
    "$top": "10"
}

# First 100 results
query_params = {
    "$filter": "Price gt 100",
    "$orderby": "Price desc",
    "$top": "100"
}
```

### Pagination with $skip

```python
# Skip first 20
query_params = {
    "$skip": "20",
    "$top": "10"
}

# Page 3 (records 21-30)
page = 3
page_size = 10
query_params = {
    "$skip": str((page - 1) * page_size),
    "$top": str(page_size)
}
```

### Continuation Tokens

```python
from localzure.services.table.advanced import QueryExecutor, parse_query_options

# First page
query_params = {
    "$filter": "Active eq true",
    "$orderby": "Name asc",
    "$top": "100"
}
options = parse_query_options(query_params)
executor = QueryExecutor()
result_set = executor.execute(entities, options)

# Next page
if result_set.continuation:
    options.continuation = result_set.continuation
    next_page = executor.execute(entities, options)
```

### Complete Pagination Example

```python
def fetch_all_pages(executor, entities, base_options):
    """Fetch all pages using continuation tokens."""
    all_results = []
    current_options = base_options
    page_num = 1
    
    while True:
        result_set = executor.execute(entities, current_options)
        all_results.extend(result_set.entities)
        
        print(f"Page {page_num}: {len(result_set.entities)} results")
        
        if not result_set.continuation:
            break
        
        current_options.continuation = result_set.continuation
        page_num += 1
    
    return all_results

# Usage
options = parse_query_options({
    "$filter": "Active eq true",
    "$orderby": "CreatedAt desc",
    "$top": "100"
})
all_results = fetch_all_pages(executor, entities, options)
```

---

## Projection and Counting

### Select Specific Properties

```python
# Single property
query_params = {
    "$select": "Name"
}

# Multiple properties
query_params = {
    "$select": "Name,Price,Category"
}

# With filter
query_params = {
    "$filter": "Price gt 100",
    "$select": "Name,Price"
}
```

### Count Only

```python
# Get count without entities
query_params = {
    "$filter": "Active eq true",
    "$count": "true"
}

# Result: result_set.count contains total, result_set.entities is empty
```

### Inline Count

```python
# Get count with entities
query_params = {
    "$filter": "Active eq true",
    "$top": "10",
    "$inlinecount": "allpages"
}

# Result: result_set.count contains total, result_set.entities contains first 10
```

### Metadata

```python
# Include type metadata
query_params = {
    "$filter": "Active eq true",
    "$top": "10"
}
options = parse_query_options(query_params)
options.metadata = True

result_set = executor.execute(entities, options)
print(result_set.metadata)
# {"properties": {"Name": {"type": "Edm.String"}, "Price": {"type": "Edm.Double"}, ...}}
```

### Combined Features

```python
# Filter + Sort + Page + Select + Count
query_params = {
    "$filter": "Category eq 'Electronics' and Price gt 100",
    "$orderby": "Price desc",
    "$top": "20",
    "$skip": "40",
    "$select": "Name,Price,Rating",
    "$inlinecount": "allpages"
}

options = parse_query_options(query_params)
result_set = executor.execute(entities, options)

print(f"Total matching: {result_set.count}")
print(f"Returned: {len(result_set.entities)}")
for entity in result_set.entities:
    print(f"{entity['Name']}: ${entity['Price']}")
```

---

## Real-World Scenarios

### E-commerce Product Search

```python
# Search for products
query_params = {
    "$filter": (
        "substringof('laptop', tolower(Name)) and "
        "Price ge 500 and Price le 2000 and "
        "Rating ge 4.0 and "
        "InStock eq true"
    ),
    "$orderby": "Rating desc, ReviewCount desc, Price asc",
    "$top": "20",
    "$select": "Name,Price,Rating,ReviewCount,ImageUrl"
}
```

### User Management

```python
# Active users created this year
query_params = {
    "$filter": (
        "Active eq true and "
        "year(CreatedAt) eq 2024 and "
        "EmailVerified eq true and "
        "not (Role eq 'Guest')"
    ),
    "$orderby": "LastLoginAt desc",
    "$select": "UserId,Email,Name,Role,LastLoginAt"
}
```

### Order Processing

```python
# Pending orders for fulfillment
query_params = {
    "$filter": (
        "(Status eq 'Pending' or Status eq 'Processing') and "
        "year(OrderDate) eq 2024 and month(OrderDate) eq 12 and "
        "TotalAmount gt 0 and "
        "ShippingAddress ne null"
    ),
    "$orderby": "Priority desc, OrderDate asc",
    "$top": "50",
    "$select": "OrderId,Status,TotalAmount,OrderDate,CustomerId"
}
```

### Analytics Query

```python
# High-value customers
query_params = {
    "$filter": (
        "TotalPurchases gt 10000 and "
        "year(LastPurchaseDate) eq 2024 and "
        "LoyaltyTier eq 'Platinum' and "
        "Active eq true"
    ),
    "$orderby": "TotalPurchases desc, LastPurchaseDate desc",
    "$select": "CustomerId,Name,Email,TotalPurchases,LoyaltyTier",
    "$inlinecount": "allpages"
}
```

### Content Moderation

```python
# Flagged content for review
query_params = {
    "$filter": (
        "Status eq 'Flagged' and "
        "year(FlaggedAt) eq 2024 and month(FlaggedAt) eq 12 and "
        "ReviewedAt eq null and "
        "FlagCount ge 3"
    ),
    "$orderby": "FlagCount desc, FlaggedAt asc",
    "$top": "100",
    "$select": "ContentId,Title,FlagCount,FlaggedAt,ReportedBy"
}
```

### Inventory Management

```python
# Low stock items
query_params = {
    "$filter": (
        "Active eq true and "
        "StockLevel lt ReorderPoint and "
        "Category ne 'Discontinued' and "
        "not (Status eq 'OrderPending')"
    ),
    "$orderby": "StockLevel asc, LastSold desc",
    "$select": "ProductId,Name,StockLevel,ReorderPoint,Category"
}
```

### Event Scheduling

```python
# Upcoming events this month
query_params = {
    "$filter": (
        "year(EventDate) eq 2024 and "
        "month(EventDate) eq 12 and "
        "day(EventDate) ge 15 and "
        "Status eq 'Confirmed' and "
        "AvailableSeats gt 0"
    ),
    "$orderby": "EventDate asc, EventTime asc",
    "$select": "EventId,Title,EventDate,EventTime,AvailableSeats,Venue"
}
```

### Compliance Audit

```python
# Documents requiring review
query_params = {
    "$filter": (
        "year(LastReviewDate) le 2023 and "
        "RequiresCompliance eq true and "
        "Status eq 'Active' and "
        "Department ne 'Archive'"
    ),
    "$orderby": "LastReviewDate asc, Priority desc",
    "$top": "50",
    "$select": "DocumentId,Title,LastReviewDate,Owner,Department",
    "$inlinecount": "allpages"
}
```

---

## Performance Patterns

### Efficient PartitionKey Queries

```python
# Best: Single partition scan
query_params = {
    "$filter": "PartitionKey eq 'users' and Active eq true"
}

# Good: Partition prefix
query_params = {
    "$filter": "startswith(PartitionKey, 'user_') and Age gt 18"
}

# Avoid: Table scan (no PartitionKey filter)
query_params = {
    "$filter": "Age gt 18"  # Scans entire table
}
```

### Index-Friendly Filters

```python
# Efficient: Equality checks first
query_params = {
    "$filter": "Category eq 'Electronics' and Price gt 100"
}

# Less efficient: Range checks first
query_params = {
    "$filter": "Price gt 100 and Category eq 'Electronics'"
}
```

### Projection for Network Efficiency

```python
# Inefficient: Return all properties
query_params = {
    "$filter": "Active eq true",
    "$top": "1000"
}

# Efficient: Only needed properties
query_params = {
    "$filter": "Active eq true",
    "$top": "1000",
    "$select": "Id,Name,Status"
}
```

### Pagination Best Practices

```python
# Good: Use $top to limit results
query_params = {
    "$filter": "Active eq true",
    "$top": "100"
}

# Better: Use continuation tokens for large datasets
options = parse_query_options(query_params)
result_set = executor.execute(entities, options)
if result_set.continuation:
    # Use continuation for next page
    pass

# Avoid: Large $skip values (inefficient)
query_params = {
    "$skip": "10000",  # Bad performance
    "$top": "100"
}
```

### Caching Strategies

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_parsed_query(filter_expr: str):
    """Cache parsed queries for reuse."""
    lexer = ODataLexer(filter_expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    optimizer = QueryOptimizer()
    return optimizer.optimize(ast)

# Reuse parsed queries
ast = get_parsed_query("Price gt 100")
evaluator = ODataEvaluator()
results = [e for e in entities if evaluator.evaluate(ast, e)]
```

### Batch Processing

```python
def process_in_batches(entities, filter_expr, batch_size=1000):
    """Process large datasets in batches."""
    ast = get_parsed_query(filter_expr)
    evaluator = ODataEvaluator()
    
    results = []
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i+batch_size]
        batch_results = [e for e in batch if evaluator.evaluate(ast, e)]
        results.extend(batch_results)
        
        print(f"Processed batch {i//batch_size + 1}: {len(batch_results)} matches")
    
    return results
```

### Monitoring Query Performance

```python
import time

def execute_with_monitoring(executor, entities, options):
    """Execute query with performance monitoring."""
    start = time.time()
    result_set = executor.execute(entities, options)
    elapsed = (time.time() - start) * 1000
    
    stats = result_set.query_stats
    print(f"Query Performance:")
    print(f"  Total time: {elapsed:.2f}ms")
    print(f"  Execution time: {stats.execution_time_ms:.2f}ms")
    print(f"  Sort time: {stats.sort_time_ms:.2f}ms")
    print(f"  Entities scanned: {stats.entities_scanned}")
    print(f"  Entities returned: {stats.entities_returned}")
    print(f"  Filter efficiency: {stats.entities_returned/stats.entities_scanned*100:.1f}%")
    
    # Alert on poor performance
    if stats.entities_scanned > 10000:
        print("  WARNING: Large table scan detected")
    
    if elapsed > 1000:
        print("  WARNING: Query took over 1 second")
    
    return result_set
```

### Parallel Query Execution

```python
from concurrent.futures import ThreadPoolExecutor
import itertools

def parallel_query(entities, filter_exprs, max_workers=4):
    """Execute multiple queries in parallel."""
    ast_cache = {expr: get_parsed_query(expr) for expr in filter_exprs}
    
    def execute_query(expr):
        ast = ast_cache[expr]
        evaluator = ODataEvaluator()
        return [e for e in entities if evaluator.evaluate(ast, e)]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(execute_query, filter_exprs))
    
    return results
```

---

## Testing Examples

### Unit Test Examples

```python
import pytest
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.evaluator import ODataEvaluator

def test_simple_comparison():
    """Test basic equality comparison."""
    lexer = ODataLexer("Name eq 'Alice'")
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    evaluator = ODataEvaluator()
    
    # Matching entity
    entity = {"Name": "Alice"}
    assert evaluator.evaluate(ast, entity) == True
    
    # Non-matching entity
    entity = {"Name": "Bob"}
    assert evaluator.evaluate(ast, entity) == False

def test_complex_filter():
    """Test complex filter with multiple conditions."""
    filter_expr = "(Price gt 10 and Price lt 100) or OnSale eq true"
    lexer = ODataLexer(filter_expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    evaluator = ODataEvaluator()
    
    # Matches price range
    assert evaluator.evaluate(ast, {"Price": 50, "OnSale": False}) == True
    
    # Matches on sale
    assert evaluator.evaluate(ast, {"Price": 200, "OnSale": True}) == True
    
    # No match
    assert evaluator.evaluate(ast, {"Price": 200, "OnSale": False}) == False

def test_string_functions():
    """Test string function evaluation."""
    filter_expr = "substringof('soft', tolower(Company))"
    lexer = ODataLexer(filter_expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    evaluator = ODataEvaluator()
    
    assert evaluator.evaluate(ast, {"Company": "Microsoft"}) == True
    assert evaluator.evaluate(ast, {"Company": "MICROSOFT"}) == True
    assert evaluator.evaluate(ast, {"Company": "Apple"}) == False
```

### Integration Test Examples

```python
def test_end_to_end_query():
    """Test complete query pipeline."""
    entities = [
        {"Name": "Product A", "Price": 50, "Category": "Electronics"},
        {"Name": "Product B", "Price": 150, "Category": "Electronics"},
        {"Name": "Product C", "Price": 30, "Category": "Books"},
    ]
    
    query_params = {
        "$filter": "Category eq 'Electronics' and Price gt 100",
        "$orderby": "Price desc",
        "$select": "Name,Price"
    }
    
    options = parse_query_options(query_params)
    executor = QueryExecutor()
    result_set = executor.execute(entities, options)
    
    assert len(result_set.entities) == 1
    assert result_set.entities[0]["Name"] == "Product B"
    assert result_set.entities[0]["Price"] == 150
    assert "Category" not in result_set.entities[0]  # Not selected
```

---

**Total Examples:** 100+

**Categories Covered:**
- Basic Comparisons (20 examples)
- Logical Operations (15 examples)
- String Functions (30 examples)
- Arithmetic Operations (15 examples)
- Date Functions (10 examples)
- Complex Queries (10 examples)
- Sorting and Pagination (15 examples)
- Projection and Counting (10 examples)
- Real-World Scenarios (8 examples)
- Performance Patterns (10 examples)
- Testing Examples (5 examples)

---

**Version:** 1.0  
**Last Updated:** December 2025  
**Maintainer:** LocalZure Team
