# OData Query Engine - API Reference

## Table of Contents

1. [Module: lexer](#module-lexer)
2. [Module: parser](#module-parser)
3. [Module: types](#module-types)
4. [Module: functions](#module-functions)
5. [Module: optimizer](#module-optimizer)
6. [Module: evaluator](#module-evaluator)
7. [Module: diagnostics](#module-diagnostics)
8. [Module: benchmark](#module-benchmark)
9. [Module: advanced](#module-advanced)

---

## Module: lexer

**Path:** `localzure.services.table.lexer`

### Classes

#### `TokenType(Enum)`

Enumeration of all token types.

**Values:**
```python
# Literals
STRING = "STRING"
NUMBER = "NUMBER"
BOOLEAN = "BOOLEAN"
NULL = "NULL"
DATETIME = "DATETIME"
GUID = "GUID"
BINARY = "BINARY"

# Operators
EQ = "EQ"           # eq
NE = "NE"           # ne
GT = "GT"           # gt
GE = "GE"           # ge
LT = "LT"           # lt
LE = "LE"           # le
AND = "AND"         # and
OR = "OR"           # or
NOT = "NOT"         # not
ADD = "ADD"         # add
SUB = "SUB"         # sub
MUL = "MUL"         # mul
DIV = "DIV"         # div
MOD = "MOD"         # mod

# Symbols
LPAREN = "LPAREN"   # (
RPAREN = "RPAREN"   # )
COMMA = "COMMA"     # ,
SLASH = "SLASH"     # /

# Other
IDENTIFIER = "IDENTIFIER"
FUNCTION = "FUNCTION"
EOF = "EOF"
```

#### `Token`

Represents a single lexical token.

**Attributes:**
- `type: TokenType` - Token type
- `value: Any` - Token value
- `position: int` - Character position in source

**Methods:**
```python
def __init__(self, type: TokenType, value: Any, position: int)
def __repr__(self) -> str
def __eq__(self, other: object) -> bool
```

**Example:**
```python
token = Token(TokenType.IDENTIFIER, "Name", 0)
print(token)  # Token(type=TokenType.IDENTIFIER, value='Name', position=0)
```

#### `ODataLexer`

Tokenizes OData filter expressions.

**Constructor:**
```python
def __init__(self, text: str)
```

**Parameters:**
- `text: str` - Filter expression to tokenize

**Methods:**

##### `tokenize() -> Generator[Token, None, None]`

Generates tokens from the input text.

**Yields:** `Token` objects

**Raises:**
- `ValueError` - On lexical errors (unclosed strings, invalid characters, etc.)

**Example:**
```python
lexer = ODataLexer("Name eq 'Alice'")
tokens = list(lexer.tokenize())
# [Token(IDENTIFIER, 'Name', 0), Token(EQ, 'eq', 5), Token(STRING, 'Alice', 8)]
```

##### `peek(offset: int = 0) -> str`

Peeks at character without consuming.

**Parameters:**
- `offset: int` - Offset from current position (default: 0)

**Returns:** Character at position or empty string if EOF

##### `advance() -> str`

Consumes and returns current character.

**Returns:** Current character or empty string if EOF

##### `skip_whitespace() -> None`

Skips whitespace characters.

##### `read_string() -> str`

Reads string literal (single-quoted).

**Returns:** String content (without quotes)

**Raises:** `ValueError` if string is unclosed

##### `read_number() -> Union[int, float]`

Reads numeric literal.

**Returns:** Integer or float value

##### `read_identifier() -> str`

Reads identifier or keyword.

**Returns:** Identifier string

**Example:**
```python
lexer = ODataLexer("Name eq 'Alice' and Age gt 30")
for token in lexer.tokenize():
    print(f"{token.type}: {token.value}")
```

---

## Module: parser

**Path:** `localzure.services.table.parser`

### Classes

#### `ASTNode` (Abstract)

Base class for all AST nodes.

**Methods:**
```python
def accept(self, visitor: 'ASTVisitor') -> Any
def __repr__(self) -> str
```

#### `Literal(ASTNode)`

Represents a literal value.

**Attributes:**
- `value: Any` - Literal value
- `edm_type: EdmType` - Edm type

**Constructor:**
```python
def __init__(self, value: Any, edm_type: Optional[EdmType] = None)
```

**Example:**
```python
node = Literal(42, EdmInt32())
```

#### `Property(ASTNode)`

Represents a property reference.

**Attributes:**
- `name: str` - Property name

**Constructor:**
```python
def __init__(self, name: str)
```

**Example:**
```python
node = Property("Name")
```

#### `BinaryOp(ASTNode)`

Represents a binary operation.

**Attributes:**
- `left: ASTNode` - Left operand
- `op: str` - Operator ("eq", "gt", "and", "add", etc.)
- `right: ASTNode` - Right operand

**Constructor:**
```python
def __init__(self, left: ASTNode, op: str, right: ASTNode)
```

**Example:**
```python
node = BinaryOp(Property("Age"), "gt", Literal(30))
```

#### `UnaryOp(ASTNode)`

Represents a unary operation.

**Attributes:**
- `op: str` - Operator ("not", "-")
- `operand: ASTNode` - Operand

**Constructor:**
```python
def __init__(self, op: str, operand: ASTNode)
```

**Example:**
```python
node = UnaryOp("not", BinaryOp(...))
```

#### `FunctionCall(ASTNode)`

Represents a function call.

**Attributes:**
- `name: str` - Function name
- `args: List[ASTNode]` - Function arguments

**Constructor:**
```python
def __init__(self, name: str, args: List[ASTNode])
```

**Example:**
```python
node = FunctionCall("substringof", [Literal("soft"), Property("Name")])
```

#### `ODataParser`

Recursive descent parser for OData expressions.

**Constructor:**
```python
def __init__(self, lexer: ODataLexer)
```

**Parameters:**
- `lexer: ODataLexer` - Lexer instance

**Methods:**

##### `parse() -> ASTNode`

Parses the input and returns AST root.

**Returns:** Root AST node

**Raises:** `SyntaxError` on parse errors

**Example:**
```python
lexer = ODataLexer("Price gt 100")
parser = ODataParser(lexer)
ast = parser.parse()
```

##### `parse_or_expr() -> ASTNode`

Parses OR expression.

##### `parse_and_expr() -> ASTNode`

Parses AND expression.

##### `parse_not_expr() -> ASTNode`

Parses NOT expression.

##### `parse_comparison_expr() -> ASTNode`

Parses comparison expression.

##### `parse_additive_expr() -> ASTNode`

Parses additive expression (add, sub).

##### `parse_multiplicative_expr() -> ASTNode`

Parses multiplicative expression (mul, div, mod).

##### `parse_unary_expr() -> ASTNode`

Parses unary expression (-, not).

##### `parse_primary_expr() -> ASTNode`

Parses primary expression (literal, property, function call, parentheses).

##### `expect(token_type: TokenType) -> Token`

Expects specific token type and consumes it.

**Parameters:**
- `token_type: TokenType` - Expected token type

**Returns:** Consumed token

**Raises:** `SyntaxError` if token doesn't match

---

## Module: types

**Path:** `localzure.services.table.types`

### Classes

#### `EdmType` (Abstract)

Base class for all Edm types.

**Methods:**

##### `validate(value: Any) -> bool`

Validates if value conforms to this type.

**Parameters:**
- `value: Any` - Value to validate

**Returns:** `True` if valid, `False` otherwise

##### `coerce(other: EdmType) -> EdmType`

Returns common type for two types.

**Parameters:**
- `other: EdmType` - Other type

**Returns:** Common type (usually promoted type)

**Raises:** `TypeError` if types incompatible

##### `is_compatible_with(other: EdmType) -> bool`

Checks if this type is compatible with another.

**Parameters:**
- `other: EdmType` - Other type

**Returns:** `True` if compatible

##### `name() -> str`

Returns Edm type name.

**Returns:** Type name (e.g., "Edm.Int32")

#### `EdmString(EdmType)`

Represents Edm.String type.

**Validation:** `isinstance(value, str)`

**Example:**
```python
edm_type = EdmString()
edm_type.validate("hello")  # True
edm_type.validate(42)       # False
```

#### `EdmInt32(EdmType)`

Represents Edm.Int32 type.

**Range:** -2,147,483,648 to 2,147,483,647

**Validation:** `isinstance(value, int) and -2**31 <= value < 2**31`

**Example:**
```python
edm_type = EdmInt32()
edm_type.validate(42)        # True
edm_type.validate(2**32)     # False (out of range)
```

#### `EdmInt64(EdmType)`

Represents Edm.Int64 type.

**Range:** -2^63 to 2^63-1

**Validation:** `isinstance(value, int) and -2**63 <= value < 2**63`

#### `EdmDouble(EdmType)`

Represents Edm.Double type.

**Validation:** `isinstance(value, (int, float))`

**Example:**
```python
edm_type = EdmDouble()
edm_type.validate(3.14)  # True
edm_type.validate(42)    # True (int promoted to double)
```

#### `EdmBoolean(EdmType)`

Represents Edm.Boolean type.

**Validation:** `isinstance(value, bool)`

#### `EdmDateTime(EdmType)`

Represents Edm.DateTime type.

**Validation:** `isinstance(value, datetime)`

**Example:**
```python
from datetime import datetime
edm_type = EdmDateTime()
edm_type.validate(datetime.now())  # True
```

#### `EdmGuid(EdmType)`

Represents Edm.Guid type.

**Format:** Standard UUID format (8-4-4-4-12 hex digits)

**Validation:** Valid UUID string

#### `EdmBinary(EdmType)`

Represents Edm.Binary type.

**Validation:** `isinstance(value, bytes)`

#### `TypeInference`

Static utility for type inference.

**Methods:**

##### `infer(value: Any) -> EdmType` (static)

Infers Edm type from Python value.

**Parameters:**
- `value: Any` - Python value

**Returns:** Corresponding `EdmType`

**Example:**
```python
TypeInference.infer(42)              # EdmInt32()
TypeInference.infer(3.14)            # EdmDouble()
TypeInference.infer("hello")         # EdmString()
TypeInference.infer(True)            # EdmBoolean()
TypeInference.infer(datetime.now())  # EdmDateTime()
```

---

## Module: functions

**Path:** `localzure.services.table.functions`

### Classes

#### `FunctionRegistry`

Registry for OData functions.

**Constructor:**
```python
def __init__(self)
```

**Methods:**

##### `register(name: str, func: Callable, arg_types: List[type], return_type: type) -> None`

Registers a function.

**Parameters:**
- `name: str` - Function name
- `func: Callable` - Function implementation
- `arg_types: List[type]` - Expected argument types
- `return_type: type` - Return type

**Example:**
```python
def custom_func(x: int) -> int:
    return x * 2

registry = FunctionRegistry()
registry.register("double", custom_func, [int], int)
```

##### `call(name: str, args: List[Any]) -> Any`

Calls a registered function.

**Parameters:**
- `name: str` - Function name
- `args: List[Any]` - Function arguments

**Returns:** Function result

**Raises:**
- `ValueError` - Unknown function or wrong argument count/types

**Example:**
```python
registry = FunctionRegistry()
result = registry.call("toupper", ["hello"])  # "HELLO"
```

##### `has(name: str) -> bool`

Checks if function is registered.

**Parameters:**
- `name: str` - Function name

**Returns:** `True` if registered

##### `get_signature(name: str) -> Tuple[List[type], type]`

Gets function signature.

**Parameters:**
- `name: str` - Function name

**Returns:** Tuple of (arg_types, return_type)

**Raises:** `ValueError` if function not found

### Built-in Functions

#### String Functions

```python
substringof(needle: str, haystack: str) -> bool
substring(s: str, pos: int, length: int = None) -> str
startswith(s: str, prefix: str) -> bool
endswith(s: str, suffix: str) -> bool
indexof(s: str, substr: str) -> int
replace(s: str, find: str, replace: str) -> str
tolower(s: str) -> str
toupper(s: str) -> str
trim(s: str) -> str
concat(s1: str, s2: str) -> str
length(s: str) -> int
```

#### Arithmetic Functions

```python
round(x: float) -> int
floor(x: float) -> int
ceiling(x: float) -> int
```

#### Date Functions

```python
year(dt: datetime) -> int
month(dt: datetime) -> int
day(dt: datetime) -> int
hour(dt: datetime) -> int
minute(dt: datetime) -> int
second(dt: datetime) -> int
```

#### Type Functions

```python
isof(value: Any, type_name: str) -> bool
```

---

## Module: optimizer

**Path:** `localzure.services.table.optimizer`

### Classes

#### `QueryOptimizer`

Optimizes AST for efficient execution.

**Constructor:**
```python
def __init__(self)
```

**Methods:**

##### `optimize(ast: ASTNode) -> ASTNode`

Optimizes AST.

**Parameters:**
- `ast: ASTNode` - Original AST

**Returns:** Optimized AST

**Optimizations:**
1. Constant folding
2. Predicate pushdown
3. Redundancy elimination
4. Short-circuit evaluation

**Example:**
```python
optimizer = QueryOptimizer()
optimized = optimizer.optimize(ast)
```

##### `get_stats() -> Dict[str, int]`

Gets optimization statistics.

**Returns:** Dictionary with:
- `constants_folded: int` - Constants folded count
- `predicates_pushed: int` - Predicates pushed count
- `redundancies_removed: int` - Redundancies removed count

**Example:**
```python
optimizer = QueryOptimizer()
optimized = optimizer.optimize(ast)
stats = optimizer.get_stats()
print(f"Folded {stats['constants_folded']} constants")
```

---

## Module: evaluator

**Path:** `localzure.services.table.evaluator`

### Classes

#### `ODataEvaluator`

Evaluates AST against entities.

**Constructor:**
```python
def __init__(self, function_registry: Optional[FunctionRegistry] = None)
```

**Parameters:**
- `function_registry: FunctionRegistry` - Custom function registry (optional)

**Methods:**

##### `evaluate(ast: ASTNode, entity: Dict[str, Any], metadata: Optional[Dict] = None) -> Any`

Evaluates AST against entity.

**Parameters:**
- `ast: ASTNode` - AST to evaluate
- `entity: Dict[str, Any]` - Entity data
- `metadata: Dict` - Optional metadata

**Returns:** Evaluation result (usually `bool` for filters)

**Raises:**
- `TypeError` - Type errors
- `ValueError` - Invalid operations
- `KeyError` - Unknown properties

**Example:**
```python
evaluator = ODataEvaluator()
entity = {"Name": "Alice", "Age": 30}
result = evaluator.evaluate(ast, entity)  # True/False
```

##### `visit_literal(node: Literal) -> Any`

Evaluates literal node.

##### `visit_property(node: Property, entity: Dict) -> Any`

Evaluates property node.

##### `visit_binary_op(node: BinaryOp, entity: Dict) -> Any`

Evaluates binary operation.

##### `visit_unary_op(node: UnaryOp, entity: Dict) -> Any`

Evaluates unary operation.

##### `visit_function_call(node: FunctionCall, entity: Dict) -> Any`

Evaluates function call.

---

## Module: diagnostics

**Path:** `localzure.services.table.diagnostics`

### Classes

#### `Diagnostic`

Represents a diagnostic message.

**Attributes:**
- `message: str` - Error message
- `position: int` - Character position
- `length: int` - Error length
- `severity: str` - "error", "warning", "info"
- `suggestion: Optional[str]` - Suggested fix

**Methods:**

##### `format(source: str) -> str`

Formats diagnostic with source context.

**Parameters:**
- `source: str` - Original source code

**Returns:** Formatted error message with visual pointer

**Example:**
```python
diag = Diagnostic("Unknown property 'Priice'", 0, 6, "error", "Did you mean 'Price'?")
print(diag.format("Priice eq 100"))
# Error at position 0-6: Unknown property 'Priice'
#   Priice eq 100
#   ^^^^^^
# Suggestion: Did you mean 'Price'?
```

#### `DiagnosticEngine`

Creates diagnostics from exceptions.

**Constructor:**
```python
def __init__(self, debug: bool = False)
```

**Parameters:**
- `debug: bool` - Enable debug output

**Methods:**

##### `diagnose(error: Exception, source: str) -> Diagnostic`

Creates diagnostic from exception.

**Parameters:**
- `error: Exception` - Exception to diagnose
- `source: str` - Source code

**Returns:** `Diagnostic` object

**Example:**
```python
engine = DiagnosticEngine()
try:
    # Parse error
    pass
except Exception as e:
    diag = engine.diagnose(e, filter_expr)
    print(diag.format(filter_expr))
```

---

## Module: benchmark

**Path:** `localzure.services.table.benchmark`

### Classes

#### `QueryBenchmark`

Performance benchmarking for queries.

**Constructor:**
```python
def __init__(self)
```

**Methods:**

##### `add_query(name: str, filter_expr: str) -> None`

Adds query to benchmark.

**Parameters:**
- `name: str` - Query name
- `filter_expr: str` - Filter expression

##### `run(entities: List[Dict], iterations: int = 1000) -> Dict[str, Dict]`

Runs benchmark.

**Parameters:**
- `entities: List[Dict]` - Test entities
- `iterations: int` - Number of iterations (default: 1000)

**Returns:** Dictionary mapping query names to statistics:
```python
{
    "query_name": {
        "mean_ms": float,
        "median_ms": float,
        "p50_ms": float,
        "p95_ms": float,
        "p99_ms": float,
        "min_ms": float,
        "max_ms": float
    }
}
```

**Example:**
```python
benchmark = QueryBenchmark()
benchmark.add_query("simple", "Price gt 100")
benchmark.add_query("complex", "(Price gt 10 and Price lt 100) or OnSale eq true")

results = benchmark.run(entities, iterations=1000)
for name, stats in results.items():
    print(f"{name}: {stats['mean_ms']:.3f}ms (p95: {stats['p95_ms']:.3f}ms)")
```

---

## Module: advanced

**Path:** `localzure.services.table.advanced`

### Classes

#### `SortDirection(Enum)`

Sort direction enum.

**Values:**
```python
ASC = "asc"
DESC = "desc"
```

#### `ResponseFormat(Enum)`

Response format enum.

**Values:**
```python
JSON = "json"
ATOM = "atom"
```

#### `ContinuationToken`

Represents a pagination continuation token.

**Attributes:**
- `partition_key: str` - Last partition key
- `row_key: str` - Last row key
- `skip_count: int` - Items skipped
- `total_scanned: int` - Total entities scanned
- `query_hash: str` - Query hash for validation

**Methods:**

##### `encode() -> str`

Encodes token to base64 string.

**Returns:** Base64-encoded token

##### `decode(token_str: str) -> ContinuationToken` (static)

Decodes token from string.

**Parameters:**
- `token_str: str` - Base64-encoded token

**Returns:** `ContinuationToken` object

**Raises:** `ValueError` if token invalid

**Example:**
```python
token = ContinuationToken("pk", "rk", 100, 500, "abc123")
encoded = token.encode()  # Base64 string
decoded = ContinuationToken.decode(encoded)
```

#### `QueryStatistics`

Query execution statistics.

**Attributes:**
- `entities_scanned: int` - Total entities scanned
- `entities_returned: int` - Entities returned
- `entities_filtered: int` - Entities filtered out
- `execution_time_ms: float` - Execution time in milliseconds
- `sort_time_ms: float` - Sort time in milliseconds
- `cache_hit: bool` - Whether query was cached

**Methods:**

##### `to_dict() -> Dict`

Converts to dictionary.

**Returns:** Dictionary representation

#### `ODataQueryOptions`

Query options container.

**Attributes:**
- `filter: Optional[str]` - $filter expression
- `select: Optional[List[str]]` - $select properties
- `orderby: Optional[List[Tuple[str, SortDirection]]]` - $orderby clauses
- `top: Optional[int]` - $top limit (0-1000)
- `skip: Optional[int]` - $skip offset (≥0)
- `count: bool` - $count flag
- `inlinecount: bool` - $inlinecount flag
- `expand: Optional[List[str]]` - $expand (reserved)
- `format: ResponseFormat` - $format
- `metadata: bool` - Include metadata
- `continuation: Optional[ContinuationToken]` - Continuation token

**Methods:**

##### `get_hash() -> str`

Gets query hash for caching.

**Returns:** 16-character SHA256 hash

##### `to_dict() -> Dict`

Converts to URL query parameters.

**Returns:** Dictionary of query parameters

**Example:**
```python
options = ODataQueryOptions(
    filter="Price gt 100",
    orderby=[("Price", SortDirection.DESC)],
    top=10,
    skip=20
)
params = options.to_dict()
# {"$filter": "Price gt 100", "$orderby": "Price desc", "$top": "10", "$skip": "20"}
```

#### `QueryResultSet`

Query result container.

**Attributes:**
- `entities: List[Dict]` - Matching entities
- `count: Optional[int]` - Total count (if requested)
- `continuation: Optional[ContinuationToken]` - Continuation token
- `query_stats: QueryStatistics` - Execution statistics
- `metadata: Optional[Dict]` - Type metadata

**Methods:**

##### `to_dict(include_stats: bool = False) -> Dict`

Converts to dictionary.

**Parameters:**
- `include_stats: bool` - Include query statistics

**Returns:** Dictionary with:
- `value: List[Dict]` - Entities
- `odata.count: int` - Total count (if present)
- `x-ms-continuation-token: str` - Continuation token (if present)
- `query_stats: Dict` - Statistics (if include_stats=True)
- `odata.metadata: Dict` - Metadata (if present)

#### `QueryExecutor`

Executes queries with advanced features.

**Constructor:**
```python
def __init__(self)
```

**Methods:**

##### `execute(entities: List[Dict], options: ODataQueryOptions, from_evaluator: Optional[List[Dict]] = None) -> QueryResultSet`

Executes query with all advanced features.

**Parameters:**
- `entities: List[Dict]` - Input entities
- `options: ODataQueryOptions` - Query options
- `from_evaluator: List[Dict]` - Pre-filtered entities (optional)

**Returns:** `QueryResultSet` with results

**Pipeline:**
1. Filter (if $filter specified)
2. Sort (if $orderby specified)
3. Skip (if $skip specified)
4. Top (if $top specified)
5. Project (if $select specified)
6. Generate continuation token (if more results)
7. Collect statistics

**Example:**
```python
executor = QueryExecutor()
options = ODataQueryOptions(
    filter="Price gt 100",
    orderby=[("Price", SortDirection.DESC)],
    top=10
)
result_set = executor.execute(entities, options)

for entity in result_set.entities:
    print(entity)

if result_set.continuation:
    # More results available
    options.continuation = result_set.continuation
    next_page = executor.execute(entities, options)
```

### Functions

#### `parse_orderby(orderby_str: str) -> List[Tuple[str, SortDirection]]`

Parses $orderby string.

**Parameters:**
- `orderby_str: str` - "$orderby" value (e.g., "Price desc,Name asc")

**Returns:** List of (property, direction) tuples

**Example:**
```python
result = parse_orderby("Price desc,Name asc")
# [("Price", SortDirection.DESC), ("Name", SortDirection.ASC)]
```

#### `parse_query_options(query_params: Dict[str, str]) -> ODataQueryOptions`

Parses query parameters into options object.

**Parameters:**
- `query_params: Dict[str, str]` - URL query parameters

**Returns:** `ODataQueryOptions` object

**Example:**
```python
params = {
    "$filter": "Price gt 100",
    "$orderby": "Price desc",
    "$top": "10",
    "$skip": "20"
}
options = parse_query_options(params)
```

---

## Usage Examples

### Complete Query Pipeline

```python
from localzure.services.table.lexer import ODataLexer
from localzure.services.table.parser import ODataParser
from localzure.services.table.optimizer import QueryOptimizer
from localzure.services.table.evaluator import ODataEvaluator
from localzure.services.table.advanced import QueryExecutor, parse_query_options

# 1. Parse query parameters
query_params = {
    "$filter": "Price gt 100",
    "$orderby": "Price desc",
    "$top": "10"
}
options = parse_query_options(query_params)

# 2. Parse and optimize filter
lexer = ODataLexer(options.filter)
parser = ODataParser(lexer)
ast = parser.parse()

optimizer = QueryOptimizer()
optimized_ast = optimizer.optimize(ast)

# 3. Filter entities
evaluator = ODataEvaluator()
filtered = [e for e in entities if evaluator.evaluate(optimized_ast, e)]

# 4. Apply advanced features
executor = QueryExecutor()
result_set = executor.execute(entities, options, from_evaluator=filtered)

# 5. Access results
print(f"Returned {len(result_set.entities)} of {result_set.count or 'unknown'} total")
for entity in result_set.entities:
    print(entity)
```

---

**Version:** 1.0  
**Last Updated:** December 2025  
**Maintainer:** LocalZure Team
