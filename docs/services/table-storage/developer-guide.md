# OData Query Engine - Developer Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Quick Start](#quick-start)
4. [Core Components](#core-components)
5. [Query Execution Pipeline](#query-execution-pipeline)
6. [Type System](#type-system)
7. [Function Library](#function-library)
8. [Query Optimization](#query-optimization)
9. [Error Handling](#error-handling)
10. [Performance Tuning](#performance-tuning)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

---

## Introduction

The LocalZure OData Query Engine provides full support for OData v3 query syntax, enabling Azure Table Storage compatible filtering, sorting, and pagination operations. This guide covers everything you need to know to use and extend the query engine.

### Features

- ✅ Complete OData v3 expression parser
- ✅ Type-safe evaluation with Edm type system
- ✅ 30+ built-in functions (string, arithmetic, date)
- ✅ Query optimization (constant folding, predicate pushdown)
- ✅ Advanced features ($orderby, $skip, $count, $metadata)
- ✅ Rich error diagnostics with suggestions
- ✅ Performance benchmarking tools
- ✅ Azure Table Storage parity

### System Requirements

- Python 3.10+
- No external dependencies (pure Python implementation)

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Query Input                            │
│              "$filter=Price gt 100"                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     Lexer                                    │
│  Tokenizes input: [IDENT(Price), GT, NUMBER(100)]          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     Parser                                   │
│  Builds AST: BinaryOp(Property('Price'), GT, Literal(100))  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Type Checker                               │
│  Validates types: Price: Int32, 100: Int32 ✓               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Optimizer                                  │
│  Simplifies: Constant folding, predicate pushdown           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Evaluator                                  │
│  Executes: Filters entities based on optimized AST         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Advanced Features                            │
│  Applies: $orderby, $skip, $top, $count, $metadata         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Result Set                                 │
│  Returns: Filtered, sorted, paginated entities             │
└─────────────────────────────────────────────────────────────┘
```

### Module Structure

```
localzure/services/table/
├── lexer.py           # Tokenization
├── parser.py          # AST construction
├── types.py           # Edm type system
├── functions.py       # Built-in functions
├── optimizer.py       # Query optimization
├── evaluator.py       # Expression evaluation
├── diagnostics.py     # Error handling
├── benchmark.py       # Performance testing
├── advanced.py        # Advanced query features
└── query.py           # Legacy filter (deprecated)
```

---

## Quick Start

### Basic Usage

```python
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.evaluator import ODataEvaluator

# Sample data
entities = [
    {"PartitionKey": "users", "RowKey": "1", "Name": "Alice", "Age": 30},
    {"PartitionKey": "users", "RowKey": "2", "Name": "Bob", "Age": 25},
    {"PartitionKey": "users", "RowKey": "3", "Name": "Charlie", "Age": 35},
]

# Parse query
filter_expr = "Age gt 25"
lexer = ODataLexer(filter_expr)
parser = ODataParser(lexer)
ast = parser.parse()

# Evaluate
evaluator = ODataEvaluator()
results = [e for e in entities if evaluator.evaluate(ast, e)]

# Results: Alice (30), Charlie (35)
print(results)
```

### Using Advanced Features

```python
from localzure.services.table.advanced import (
    QueryExecutor,
    ODataQueryOptions,
    parse_query_options
)

# Parse query parameters
query_params = {
    "$filter": "Age gt 25",
    "$orderby": "Age desc",
    "$top": "2",
    "$select": "Name,Age"
}
options = parse_query_options(query_params)

# Execute query
executor = QueryExecutor()
result_set = executor.execute(entities, options)

# Access results
print(result_set.entities)  # [{"Name": "Charlie", "Age": 35, ...}, ...]
print(result_set.count)     # Total count if requested
print(result_set.continuation)  # Continuation token if more results
```

---

## Core Components

### 1. Lexer (Tokenization)

**Purpose:** Breaks query string into tokens.

**Key Classes:**
- `TokenType`: Enum of all token types
- `Token`: Represents a single token (type, value, position)
- `ODataLexer`: Main tokenizer

**Example:**

```python
from localzure.services.table.lexer import ODataLexer, TokenType

lexer = ODataLexer("Name eq 'Alice'")
tokens = list(lexer.tokenize())

# [
#   Token(type=TokenType.IDENTIFIER, value='Name', position=0),
#   Token(type=TokenType.EQ, value='eq', position=5),
#   Token(type=TokenType.STRING, value='Alice', position=8)
# ]
```

**Error Handling:**

```python
try:
    lexer = ODataLexer("Name eq 'unclosed")
    tokens = list(lexer.tokenize())
except ValueError as e:
    print(e)  # "Unclosed string literal at position 8"
```

### 2. Parser (AST Construction)

**Purpose:** Builds Abstract Syntax Tree from tokens.

**Key Classes:**
- `ASTNode`: Base class for all AST nodes
- `BinaryOp`, `UnaryOp`, `Literal`, `Property`, `FunctionCall`: Node types
- `ODataParser`: Recursive descent parser

**Example:**

```python
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser

lexer = ODataLexer("(Age gt 20) and (Name eq 'Alice')")
parser = ODataParser(lexer)
ast = parser.parse()

# AST structure:
# BinaryOp(
#     left=BinaryOp(Property('Age'), GT, Literal(20)),
#     op=AND,
#     right=BinaryOp(Property('Name'), EQ, Literal('Alice'))
# )
```

**Parser Methods:**
- `parse()`: Entry point, returns AST root
- `parse_or_expr()`: Handles OR operations
- `parse_and_expr()`: Handles AND operations
- `parse_comparison_expr()`: Handles comparisons
- `parse_additive_expr()`: Handles +/- operations
- `parse_multiplicative_expr()`: Handles */% operations
- `parse_unary_expr()`: Handles unary minus/NOT
- `parse_primary_expr()`: Handles literals, properties, functions, parentheses

### 3. Type System

**Purpose:** Provides Edm type definitions and validation.

**Key Classes:**
- `EdmType`: Base type class
- `EdmString`, `EdmInt32`, `EdmInt64`, `EdmDouble`, `EdmBoolean`, `EdmDateTime`, `EdmGuid`, `EdmBinary`: Concrete types
- `TypeInference`: Infers types from Python values

**Example:**

```python
from localzure.services.table.types import EdmInt32, EdmString, TypeInference

# Type validation
int_type = EdmInt32()
print(int_type.validate(42))      # True
print(int_type.validate("42"))    # False

# Type inference
inferred = TypeInference.infer(42)
print(inferred)  # EdmInt32()

# Type coercion
int32 = EdmInt32()
int64 = EdmInt64()
result_type = int32.coerce(int64)
print(result_type)  # EdmInt64() (promotes to larger type)
```

**Type Compatibility:**

```python
from localzure.services.table.types import EdmInt32, EdmDouble

int_type = EdmInt32()
double_type = EdmDouble()

# Numeric promotion
print(int_type.is_compatible_with(double_type))  # True (can promote)
print(double_type.is_compatible_with(int_type))  # False (can't demote)
```

### 4. Function Library

**Purpose:** Implements OData built-in functions.

**Categories:**
1. String functions (10)
2. Arithmetic functions (3)
3. Date functions (6)
4. Type functions (1)

**Example:**

```python
from localzure.services.table.functions import FunctionRegistry

registry = FunctionRegistry()

# String functions
result = registry.call("substringof", ["micro", "Microsoft"])  # True
result = registry.call("toupper", ["hello"])  # "HELLO"
result = registry.call("substring", ["hello", 1, 3])  # "ell"

# Arithmetic functions
result = registry.call("round", [3.14159])  # 3
result = registry.call("ceiling", [2.1])  # 3

# Date functions
from datetime import datetime
dt = datetime(2024, 6, 15, 14, 30, 45)
result = registry.call("year", [dt])  # 2024
result = registry.call("month", [dt])  # 6
```

**Available Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `substringof(s1, s2)` | `(str, str) -> bool` | Check if s1 in s2 |
| `substring(s, pos[, len])` | `(str, int[, int]) -> str` | Extract substring |
| `startswith(s, prefix)` | `(str, str) -> bool` | Check prefix |
| `endswith(s, suffix)` | `(str, str) -> bool` | Check suffix |
| `indexof(s, substr)` | `(str, str) -> int` | Find substring index |
| `replace(s, find, repl)` | `(str, str, str) -> str` | Replace substring |
| `tolower(s)` | `(str) -> str` | Convert to lowercase |
| `toupper(s)` | `(str) -> str` | Convert to uppercase |
| `trim(s)` | `(str) -> str` | Trim whitespace |
| `concat(s1, s2)` | `(str, str) -> str` | Concatenate |
| `length(s)` | `(str) -> int` | String length |
| `round(x)` | `(num) -> int` | Round to nearest |
| `floor(x)` | `(num) -> int` | Round down |
| `ceiling(x)` | `(num) -> int` | Round up |
| `year(dt)` | `(datetime) -> int` | Extract year |
| `month(dt)` | `(datetime) -> int` | Extract month |
| `day(dt)` | `(datetime) -> int` | Extract day |
| `hour(dt)` | `(datetime) -> int` | Extract hour |
| `minute(dt)` | `(datetime) -> int` | Extract minute |
| `second(dt)` | `(datetime) -> int` | Extract second |
| `isof(value, type)` | `(any, str) -> bool` | Type check |

### 5. Optimizer

**Purpose:** Optimizes AST for faster execution.

**Optimizations:**
1. **Constant Folding:** Evaluate constant expressions at parse time
2. **Predicate Pushdown:** Move filters closer to data
3. **Redundancy Elimination:** Remove duplicate/unnecessary conditions
4. **Short-Circuit Evaluation:** Optimize AND/OR chains

**Example:**

```python
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.optimizer import QueryOptimizer

# Original query with constants
filter_expr = "Price gt (10 add 5) and Active eq true"
lexer = ODataLexer(filter_expr)
parser = ODataParser(lexer)
ast = parser.parse()

# Optimize
optimizer = QueryOptimizer()
optimized_ast = optimizer.optimize(ast)

# Result: Price gt 15 and Active eq true
# (10 add 5) was folded to 15 at parse time
```

**Optimization Statistics:**

```python
optimizer = QueryOptimizer()
optimized_ast = optimizer.optimize(ast)

stats = optimizer.get_stats()
print(stats["constants_folded"])      # Number of constants folded
print(stats["predicates_pushed"])     # Number of predicates optimized
print(stats["redundancies_removed"])  # Number of redundancies eliminated
```

### 6. Evaluator

**Purpose:** Executes optimized AST against entities.

**Key Classes:**
- `ODataEvaluator`: Main evaluation engine
- `EvaluationContext`: Holds entity and metadata during evaluation

**Example:**

```python
from localzure.services.table.evaluator import ODataEvaluator

evaluator = ODataEvaluator()
entity = {"Name": "Alice", "Age": 30, "Active": True}

# Simple comparison
result = evaluator.evaluate(ast, entity)  # True/False

# With metadata
result = evaluator.evaluate(ast, entity, metadata={"schema": "..."})
```

**Null Handling:**

```python
entity = {"Name": "Alice", "Age": None}

# null eq null -> True
# null ne <value> -> True
# null in arithmetic -> null
# null in logical -> depends on operation
```

---

## Query Execution Pipeline

### Step-by-Step Execution

```python
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.optimizer import QueryOptimizer
from localzure.services.table.evaluator import ODataEvaluator
from localzure.services.table.advanced import QueryExecutor, parse_query_options

# 1. Parse query parameters
query_params = {
    "$filter": "(Price gt 10 and Price lt 100) or OnSale eq true",
    "$orderby": "Price desc",
    "$top": "10",
    "$skip": "20",
    "$select": "Name,Price,Category"
}
options = parse_query_options(query_params)

# 2. Parse filter expression
lexer = ODataLexer(options.filter)
parser = ODataParser(lexer)
ast = parser.parse()

# 3. Optimize
optimizer = QueryOptimizer()
optimized_ast = optimizer.optimize(ast)

# 4. Filter entities
evaluator = ODataEvaluator()
filtered = [e for e in entities if evaluator.evaluate(optimized_ast, e)]

# 5. Apply advanced features
executor = QueryExecutor()
result_set = executor.execute(filtered, options)

# 6. Access results
for entity in result_set.entities:
    print(entity["Name"], entity["Price"])

# Check for more results
if result_set.continuation:
    # Fetch next page using continuation token
    next_options = options
    next_options.continuation = result_set.continuation
    next_results = executor.execute(entities, next_options)
```

### Performance Metrics

```python
import time

start = time.time()
result_set = executor.execute(entities, options)
elapsed = time.time() - start

print(f"Scanned: {result_set.query_stats.entities_scanned}")
print(f"Returned: {result_set.query_stats.entities_returned}")
print(f"Filtered: {result_set.query_stats.entities_filtered}")
print(f"Execution time: {result_set.query_stats.execution_time_ms:.2f}ms")
print(f"Sort time: {result_set.query_stats.sort_time_ms:.2f}ms")
```

---

## Type System

### Edm Type Hierarchy

```
EdmType (abstract)
├── EdmString
├── EdmInt32
├── EdmInt64
├── EdmDouble
├── EdmBoolean
├── EdmDateTime
├── EdmGuid
└── EdmBinary
```

### Type Inference

```python
from localzure.services.table.types import TypeInference

# Automatic inference
TypeInference.infer(42)          # EdmInt32
TypeInference.infer(42.5)        # EdmDouble
TypeInference.infer("hello")     # EdmString
TypeInference.infer(True)        # EdmBoolean
TypeInference.infer(datetime.now())  # EdmDateTime
```

### Type Validation

```python
from localzure.services.table.types import EdmInt32, EdmString

int_type = EdmInt32()
str_type = EdmString()

# Valid
int_type.validate(42)       # True
str_type.validate("hello")  # True

# Invalid
int_type.validate("42")     # False
int_type.validate(2**32)    # False (out of range)
```

### Type Coercion

```python
from localzure.services.table.types import EdmInt32, EdmInt64, EdmDouble

# Numeric promotion
EdmInt32().coerce(EdmInt64())   # EdmInt64
EdmInt32().coerce(EdmDouble())  # EdmDouble
EdmInt64().coerce(EdmDouble())  # EdmDouble

# No demotion
EdmDouble().coerce(EdmInt32())  # Raises TypeError
```

---

## Function Library

### String Functions

```python
from localzure.services.table.functions import FunctionRegistry

registry = FunctionRegistry()

# substringof: Check if substring exists
registry.call("substringof", ["soft", "Microsoft"])  # True

# substring: Extract substring
registry.call("substring", ["hello", 1])      # "ello"
registry.call("substring", ["hello", 1, 3])   # "ell"

# startswith/endswith
registry.call("startswith", ["hello", "hel"])  # True
registry.call("endswith", ["hello", "lo"])     # True

# indexof: Find substring
registry.call("indexof", ["hello", "ll"])  # 2
registry.call("indexof", ["hello", "x"])   # -1

# replace: Replace substring
registry.call("replace", ["hello", "ll", "r"])  # "hero"

# Case conversion
registry.call("tolower", ["HELLO"])  # "hello"
registry.call("toupper", ["hello"])  # "HELLO"

# trim: Remove whitespace
registry.call("trim", ["  hello  "])  # "hello"

# concat: Concatenate strings
registry.call("concat", ["hello", " world"])  # "hello world"

# length: String length
registry.call("length", ["hello"])  # 5
```

### Arithmetic Functions

```python
# round: Round to nearest integer
registry.call("round", [3.14159])  # 3
registry.call("round", [3.5])      # 4

# floor: Round down
registry.call("floor", [3.9])  # 3

# ceiling: Round up
registry.call("ceiling", [3.1])  # 4
```

### Date Functions

```python
from datetime import datetime

dt = datetime(2024, 6, 15, 14, 30, 45)

# Extract components
registry.call("year", [dt])    # 2024
registry.call("month", [dt])   # 6
registry.call("day", [dt])     # 15
registry.call("hour", [dt])    # 14
registry.call("minute", [dt])  # 30
registry.call("second", [dt])  # 45
```

---

## Query Optimization

### Optimization Techniques

#### 1. Constant Folding

```python
# Before: Price gt (10 add 5)
# After:  Price gt 15

# Before: length('hello') eq 5
# After:  true
```

#### 2. Predicate Pushdown

```python
# Before: (Price gt 10) and (Category eq 'Electronics')
# After:  Evaluates Category first (usually more selective)
```

#### 3. Redundancy Elimination

```python
# Before: (Price gt 10) and (Price gt 10)
# After:  Price gt 10

# Before: (Active eq true) and true
# After:  Active eq true
```

#### 4. Short-Circuit Evaluation

```python
# false and <anything> -> false (doesn't evaluate right side)
# true or <anything> -> true (doesn't evaluate right side)
```

### Benchmarking

```python
from localzure.services.table.benchmark import QueryBenchmark

benchmark = QueryBenchmark()

# Add queries to benchmark
benchmark.add_query("simple", "Price gt 100")
benchmark.add_query("complex", "(Price gt 10 and Price lt 100) or OnSale eq true")

# Run benchmarks
results = benchmark.run(entities, iterations=1000)

for name, stats in results.items():
    print(f"{name}:")
    print(f"  Mean: {stats['mean_ms']:.3f}ms")
    print(f"  P50:  {stats['p50_ms']:.3f}ms")
    print(f"  P95:  {stats['p95_ms']:.3f}ms")
    print(f"  P99:  {stats['p99_ms']:.3f}ms")
```

---

## Error Handling

### Error Types

#### 1. Lexical Errors

```python
from localzure.services.table.lexer import ODataLexer

try:
    lexer = ODataLexer("Name eq 'unclosed")
    tokens = list(lexer.tokenize())
except ValueError as e:
    print(e)  # "Unclosed string literal at position 8"
```

#### 2. Syntax Errors

```python
from localzure.services.table.parser import ODataParser

try:
    lexer = ODataLexer("Name eq")
    parser = ODataParser(lexer)
    ast = parser.parse()
except SyntaxError as e:
    print(e)  # "Expected value after 'eq' at position 7"
```

#### 3. Type Errors

```python
from localzure.services.table.evaluator import ODataEvaluator

try:
    # Comparing string with number
    ast = parser.parse_expr("Name gt 100")
    evaluator = ODataEvaluator()
    result = evaluator.evaluate(ast, entity)
except TypeError as e:
    print(e)  # "Cannot compare Edm.String with Edm.Int32"
```

#### 4. Runtime Errors

```python
try:
    # Division by zero
    ast = parser.parse_expr("Price div 0")
    result = evaluator.evaluate(ast, entity)
except ZeroDivisionError as e:
    print(e)  # "Division by zero"
```

### Rich Diagnostics

```python
from localzure.services.table.diagnostics import DiagnosticEngine

engine = DiagnosticEngine()

try:
    filter_expr = "Priice eq 'Alice'"  # Typo
    lexer = ODataLexer(filter_expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
except Exception as e:
    diagnostic = engine.diagnose(e, filter_expr)
    print(diagnostic.format())

# Output:
# Error at position 0-6: Unknown property 'Priice'
#   Priice eq 'Alice'
#   ^^^^^^
# Suggestion: Did you mean 'Price'?
```

---

## Performance Tuning

### Best Practices

#### 1. Use PartitionKey Filters

```python
# Good: Scans single partition
"PartitionKey eq 'users' and Age gt 30"

# Bad: Scans entire table
"Age gt 30"
```

#### 2. Limit Result Size

```python
# Always use $top for large result sets
query_params = {
    "$filter": "Active eq true",
    "$top": "100"  # Limit to 100 results
}
```

#### 3. Use Projection

```python
# Only select needed properties
query_params = {
    "$filter": "Price gt 100",
    "$select": "Name,Price"  # Don't return all properties
}
```

#### 4. Cache Query Objects

```python
# Parse once, reuse many times
lexer = ODataLexer("Price gt 100")
parser = ODataParser(lexer)
ast = parser.parse()
optimizer = QueryOptimizer()
optimized_ast = optimizer.optimize(ast)

# Reuse for multiple entities
evaluator = ODataEvaluator()
for entity in entities:
    if evaluator.evaluate(optimized_ast, entity):
        results.append(entity)
```

#### 5. Use Continuation Tokens

```python
# For large result sets
def fetch_all_pages(executor, entities, options):
    all_results = []
    current_options = options
    
    while True:
        result_set = executor.execute(entities, current_options)
        all_results.extend(result_set.entities)
        
        if not result_set.continuation:
            break
        
        current_options.continuation = result_set.continuation
    
    return all_results
```

### Performance Monitoring

```python
from localzure.services.table.advanced import QueryExecutor

executor = QueryExecutor()
result_set = executor.execute(entities, options)

# Check statistics
stats = result_set.query_stats
print(f"Scanned: {stats.entities_scanned}")
print(f"Filtered: {stats.entities_filtered}")
print(f"Filter efficiency: {stats.entities_returned / stats.entities_scanned * 100:.1f}%")

# Alert if scan is too large
if stats.entities_scanned > 10000:
    print("WARNING: Large table scan detected. Consider adding PartitionKey filter.")
```

---

## Testing

### Unit Testing

```python
import pytest
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser

def test_simple_comparison():
    lexer = ODataLexer("Price gt 100")
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    assert ast.op == "gt"
    assert ast.left.name == "Price"
    assert ast.right.value == 100

def test_complex_expression():
    expr = "(Price gt 10 and Price lt 100) or OnSale eq true"
    lexer = ODataLexer(expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    assert ast.op == "or"
    assert ast.left.op == "and"
```

### Integration Testing

```python
def test_end_to_end_query():
    entities = [
        {"PartitionKey": "products", "RowKey": "1", "Name": "Widget", "Price": 50},
        {"PartitionKey": "products", "RowKey": "2", "Name": "Gadget", "Price": 150},
    ]
    
    query_params = {
        "$filter": "Price gt 100",
        "$orderby": "Price desc",
        "$top": "10"
    }
    
    options = parse_query_options(query_params)
    executor = QueryExecutor()
    result_set = executor.execute(entities, options)
    
    assert len(result_set.entities) == 1
    assert result_set.entities[0]["Name"] == "Gadget"
```

### Property-Based Testing

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=-1000, max_value=1000))
def test_arithmetic_operations(n):
    expr = f"Price add {n}"
    lexer = ODataLexer(expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    
    evaluator = ODataEvaluator()
    entity = {"Price": 100}
    result = evaluator.evaluate(ast, entity)
    
    assert result == 100 + n
```

---

## Troubleshooting

### Common Issues

#### Issue 1: "Unknown property 'X'"

**Cause:** Property name typo or property doesn't exist in entity.

**Solution:**
```python
# Check available properties
entity = {"Name": "Alice", "Age": 30}
print(entity.keys())  # ['Name', 'Age']

# Use correct property name (case-sensitive)
filter_expr = "Name eq 'Alice'"  # Correct
# filter_expr = "name eq 'Alice'"  # Wrong (case mismatch)
```

#### Issue 2: Type mismatch errors

**Cause:** Comparing incompatible types.

**Solution:**
```python
# Wrong: Comparing string with number
"Name gt 100"

# Correct: Compare with appropriate type
"Age gt 100"

# Use type conversion functions if needed
"tolower(Name) eq 'alice'"
```

#### Issue 3: Poor query performance

**Cause:** Missing PartitionKey filter or large table scan.

**Solution:**
```python
# Add PartitionKey to filter
query_params = {
    "$filter": "PartitionKey eq 'users' and Age gt 30"
}

# Use $top to limit results
query_params["$top"] = "100"

# Monitor scan size
if result_set.query_stats.entities_scanned > 10000:
    print("Consider optimizing query")
```

#### Issue 4: Unclosed string literals

**Cause:** Missing closing quote.

**Solution:**
```python
# Wrong
"Name eq 'Alice"

# Correct
"Name eq 'Alice'"

# Escaping quotes
"Name eq 'O''Brien'"  # O'Brien
```

#### Issue 5: Function argument errors

**Cause:** Wrong number or type of arguments.

**Solution:**
```python
# Check function signature
# substring(string, position) or substring(string, position, length)

# Wrong
"substring(Name)"  # Missing position

# Correct
"substring(Name, 0, 5)"
```

### Debug Mode

```python
from localzure.services.table.diagnostics import DiagnosticEngine

# Enable debug mode
engine = DiagnosticEngine(debug=True)

# Parse with diagnostics
try:
    lexer = ODataLexer(filter_expr)
    tokens = list(lexer.tokenize())
    print("Tokens:", tokens)
    
    parser = ODataParser(lexer)
    ast = parser.parse()
    print("AST:", ast)
    
    optimizer = QueryOptimizer()
    optimized = optimizer.optimize(ast)
    print("Optimized:", optimized)
    
except Exception as e:
    diagnostic = engine.diagnose(e, filter_expr)
    print(diagnostic.format())
```

---

## Advanced Topics

### Custom Functions

```python
from localzure.services.table.functions import FunctionRegistry

# Register custom function
registry = FunctionRegistry()

def custom_hash(value: str) -> int:
    return hash(value) % 1000

registry.register("myhash", custom_hash, arg_types=[str], return_type=int)

# Use in queries
"myhash(Name) eq 42"
```

### Query Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def parse_cached(filter_expr: str):
    lexer = ODataLexer(filter_expr)
    parser = ODataParser(lexer)
    ast = parser.parse()
    optimizer = QueryOptimizer()
    return optimizer.optimize(ast)

# Reuse parsed queries
ast = parse_cached("Price gt 100")
```

### Parallel Evaluation

```python
from concurrent.futures import ThreadPoolExecutor

def evaluate_chunk(chunk, ast):
    evaluator = ODataEvaluator()
    return [e for e in chunk if evaluator.evaluate(ast, e)]

# Split entities into chunks
chunk_size = 1000
chunks = [entities[i:i+chunk_size] for i in range(0, len(entities), chunk_size)]

# Evaluate in parallel
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(evaluate_chunk, chunk, ast) for chunk in chunks]
    results = []
    for future in futures:
        results.extend(future.result())
```

---

## Resources

- [OData Grammar Specification](./odata-grammar.md)
- [API Reference](./api-reference.md)
- [Example Library](./examples.md)
- [Azure Table Storage Documentation](https://learn.microsoft.com/en-us/rest/api/storageservices/querying-tables-and-entities)

---

**Version:** 1.0  
**Last Updated:** December 2025  
**Maintainer:** LocalZure Team
