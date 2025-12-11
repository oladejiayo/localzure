# OData Query Language - Formal Grammar

## Overview

This document defines the formal grammar for the OData v3 query language subset supported by LocalZure Table Storage. The grammar is specified in Extended Backus-Naur Form (EBNF).

## Notation

- `::=` : Definition
- `|` : Alternation (OR)
- `()` : Grouping
- `[]` : Optional (zero or one)
- `{}` : Repetition (zero or more)
- `""` : Terminal string
- `''` : Terminal character
- `<>` : Non-terminal symbol

## Grammar Rules

### Query Expression

```ebnf
<query> ::= <filter_expr>

<filter_expr> ::= <or_expr>

<or_expr> ::= <and_expr> { "or" <and_expr> }

<and_expr> ::= <not_expr> { "and" <not_expr> }

<not_expr> ::= ["not"] <comparison_expr>

<comparison_expr> ::= <add_expr> [ <comparison_op> <add_expr> ]

<comparison_op> ::= "eq" | "ne" | "gt" | "ge" | "lt" | "le"

<add_expr> ::= <mult_expr> { <add_op> <mult_expr> }

<add_op> ::= "add" | "sub"

<mult_expr> ::= <unary_expr> { <mult_op> <unary_expr> }

<mult_op> ::= "mul" | "div" | "mod"

<unary_expr> ::= ["-"] <primary_expr>

<primary_expr> ::= <literal>
                 | <property_path>
                 | <function_call>
                 | "(" <filter_expr> ")"
```

### Literals

```ebnf
<literal> ::= <string_literal>
            | <number_literal>
            | <boolean_literal>
            | <null_literal>
            | <datetime_literal>
            | <guid_literal>
            | <binary_literal>

<string_literal> ::= "'" { <string_char> } "'"

<string_char> ::= <any_char_except_single_quote>
                | "''"  (* Escaped single quote *)

<number_literal> ::= <integer_literal>
                   | <decimal_literal>
                   | <double_literal>
                   | <int64_literal>

<integer_literal> ::= ["-"] <digit> { <digit> }

<decimal_literal> ::= ["-"] <digit> { <digit> } "." <digit> { <digit> } ["M" | "m"]

<double_literal> ::= ["-"] <digit> { <digit> } "." <digit> { <digit> } ["D" | "d"]

<int64_literal> ::= ["-"] <digit> { <digit> } ("L" | "l")

<boolean_literal> ::= "true" | "false"

<null_literal> ::= "null"

<datetime_literal> ::= "datetime'" <datetime_value> "'"

<datetime_value> ::= <year> "-" <month> "-" <day> ["T" <hour> ":" <minute> [":" <second> ["." <fraction>]]]

<guid_literal> ::= "guid'" <guid_value> "'"

<guid_value> ::= <hex>{8} "-" <hex>{4} "-" <hex>{4} "-" <hex>{4} "-" <hex>{12}

<binary_literal> ::= "binary'" <base64_value> "'" | "X'" <hex_value> "'"
```

### Property Paths

```ebnf
<property_path> ::= <identifier> { "/" <identifier> }

<identifier> ::= <letter> { <letter> | <digit> | "_" }

<letter> ::= "A" .. "Z" | "a" .. "z"

<digit> ::= "0" .. "9"

<hex> ::= <digit> | "A" .. "F" | "a" .. "f"
```

### Function Calls

```ebnf
<function_call> ::= <function_name> "(" [<argument_list>] ")"

<function_name> ::= <string_function>
                  | <arithmetic_function>
                  | <date_function>
                  | <type_function>

<argument_list> ::= <filter_expr> { "," <filter_expr> }
```

### String Functions

```ebnf
<string_function> ::= "substringof" | "substring" | "startswith" | "endswith"
                    | "indexof" | "replace" | "tolower" | "toupper"
                    | "trim" | "concat" | "length"
```

### Arithmetic Functions

```ebnf
<arithmetic_function> ::= "round" | "floor" | "ceiling"
```

### Date Functions

```ebnf
<date_function> ::= "year" | "month" | "day" | "hour" | "minute" | "second"
```

### Type Functions

```ebnf
<type_function> ::= "isof"
```

### Query Options

```ebnf
<query_options> ::= "?" <query_option> { "&" <query_option> }

<query_option> ::= <filter_option>
                 | <select_option>
                 | <orderby_option>
                 | <top_option>
                 | <skip_option>
                 | <count_option>
                 | <inlinecount_option>
                 | <format_option>

<filter_option> ::= "$filter=" <filter_expr>

<select_option> ::= "$select=" <property_list>

<property_list> ::= <identifier> { "," <identifier> }

<orderby_option> ::= "$orderby=" <orderby_list>

<orderby_list> ::= <orderby_item> { "," <orderby_item> }

<orderby_item> ::= <identifier> [ "asc" | "desc" ]

<top_option> ::= "$top=" <integer_literal>

<skip_option> ::= "$skip=" <integer_literal>

<count_option> ::= "$count=" <boolean_literal>

<inlinecount_option> ::= "$inlinecount=" ("allpages" | "none")

<format_option> ::= "$format=" ("json" | "atom")
```

## Lexical Tokens

### Keywords

Reserved words that cannot be used as identifiers:

```
and, or, not, eq, ne, gt, ge, lt, le, add, sub, mul, div, mod
true, false, null
datetime, guid, binary
substringof, substring, startswith, endswith, indexof, replace
tolower, toupper, trim, concat, length
round, floor, ceiling
year, month, day, hour, minute, second
isof
```

### Operators

```
Comparison: eq, ne, gt, ge, lt, le
Logical: and, or, not
Arithmetic: add, sub, mul, div, mod
Unary: -
```

### Delimiters

```
Parentheses: ( )
String quotes: '
Comma: ,
Slash: /
```

## Operator Precedence

From highest to lowest:

1. Primary expressions (literals, property paths, function calls, parentheses)
2. Unary minus (`-`)
3. Multiplicative (`mul`, `div`, `mod`)
4. Additive (`add`, `sub`)
5. Comparison (`eq`, `ne`, `gt`, `ge`, `lt`, `le`)
6. Logical NOT (`not`)
7. Logical AND (`and`)
8. Logical OR (`or`)

## Type System

### Edm Types

```ebnf
<edm_type> ::= "Edm.Binary"
             | "Edm.Boolean"
             | "Edm.DateTime"
             | "Edm.Double"
             | "Edm.Guid"
             | "Edm.Int32"
             | "Edm.Int64"
             | "Edm.String"
```

### Type Coercion Rules

1. **Numeric Promotion:**
   - `Int32` → `Int64` → `Double`
   - Automatic promotion in mixed-type arithmetic

2. **String Comparison:**
   - Case-sensitive by default
   - Use `tolower()` or `toupper()` for case-insensitive

3. **DateTime Arithmetic:**
   - Not supported (use date functions instead)

4. **Boolean Operations:**
   - No automatic conversion to/from other types
   - `null` is distinct from `false`

## Semantic Rules

### Property Resolution

1. Property names are case-sensitive
2. System properties: `PartitionKey`, `RowKey`, `Timestamp`
3. User properties: Any valid identifier
4. Property paths support navigation (future: complex types)

### Null Handling

1. `null` comparisons:
   - `null eq null` → `true`
   - `null eq <any_value>` → `false`
   - `null ne <any_value>` → `true`

2. `null` in arithmetic:
   - Any arithmetic operation with `null` → `null`

3. `null` in logical operations:
   - `null and true` → `null`
   - `null and false` → `false`
   - `null or true` → `true`
   - `null or false` → `null`
   - `not null` → `null`

### String Functions

- `substringof(s1, s2)`: Returns `true` if `s1` is a substring of `s2`
- `substring(s, pos)`: Returns substring starting at `pos`
- `substring(s, pos, len)`: Returns substring of length `len` starting at `pos`
- `startswith(s, prefix)`: Returns `true` if `s` starts with `prefix`
- `endswith(s, suffix)`: Returns `true` if `s` ends with `suffix`
- `indexof(s, substr)`: Returns 0-based index of `substr` in `s`, or -1
- `replace(s, find, replace)`: Replaces all occurrences of `find` with `replace`
- `tolower(s)`: Converts to lowercase
- `toupper(s)`: Converts to uppercase
- `trim(s)`: Removes leading/trailing whitespace
- `concat(s1, s2)`: Concatenates strings
- `length(s)`: Returns string length

### Date Functions

- `year(dt)`: Extracts year (e.g., 2024)
- `month(dt)`: Extracts month (1-12)
- `day(dt)`: Extracts day (1-31)
- `hour(dt)`: Extracts hour (0-23)
- `minute(dt)`: Extracts minute (0-59)
- `second(dt)`: Extracts second (0-59)

### Arithmetic Functions

- `round(x)`: Rounds to nearest integer
- `floor(x)`: Rounds down to integer
- `ceiling(x)`: Rounds up to integer

## Examples

### Basic Filters

```odata
PartitionKey eq 'users'
Price gt 100
Active eq true
Name ne null
```

### Complex Filters

```odata
(Price gt 10 and Price lt 100) or Category eq 'Sale'
not (Status eq 'Deleted')
Rating ge 4.5 and Reviews gt 100
```

### String Operations

```odata
substringof('micro', tolower(Company))
startswith(Name, 'John')
length(Description) gt 500
```

### Arithmetic

```odata
(Price mul Quantity) gt 1000
Rating add Bonus gt 10
Amount mod 100 eq 0
```

### Date Filters

```odata
year(CreatedAt) eq 2024
month(OrderDate) ge 6
day(Timestamp) le 15
```

### Query Options

```
$filter=Price gt 100
$select=Name,Price,Category
$orderby=Price desc,Name asc
$top=10
$skip=20
$count=true
$inlinecount=allpages
$format=json
```

## Limitations

### Not Supported in v1

1. **Navigation Properties:** Complex type navigation (e.g., `Address/City`)
2. **$expand:** Related entity expansion
3. **Geo Functions:** `geo.distance()`, etc.
4. **Lambda Operators:** `any()`, `all()`
5. **Case-Insensitive Hints:** Must use `tolower()`/`toupper()`
6. **Duration/TimeOfDay:** Only `DateTime` supported
7. **Collection Operations:** Array/collection functions

### Azure Table Storage Specific

1. **Partition Scans:** Queries without `PartitionKey` scan entire table
2. **Continuation Tokens:** Required for results > 1000
3. **Property Count:** Max 252 properties per entity
4. **Property Size:** Max 64KB per property, 1MB per entity
5. **Query Timeout:** 30 seconds default

## Error Handling

### Syntax Errors

- Unexpected token
- Unclosed string literal
- Invalid function call
- Mismatched parentheses

### Semantic Errors

- Unknown property reference
- Type mismatch in operation
- Invalid function argument count
- Invalid function argument type
- Division by zero
- Invalid date/time format

### Runtime Errors

- Property value exceeds type bounds
- String too long for operation
- Timeout exceeded
- Memory limit exceeded

## Performance Considerations

### Query Optimization

1. **Filter Early:** Put most selective filters first
2. **Use PartitionKey:** Dramatically reduces scan scope
3. **Avoid Scans:** Prefer point queries when possible
4. **Index Hints:** All properties are indexed
5. **Function Overhead:** String functions slower than comparisons

### Best Practices

1. Always include `PartitionKey` in filters when possible
2. Use `$top` to limit result set size
3. Use continuation tokens for large results
4. Cache query objects for repeated use
5. Use `$select` to reduce data transfer
6. Combine `$filter` and `$orderby` carefully (sorts after filter)

## Compliance

This grammar is compliant with:
- OData v3 specification (subset)
- Azure Table Storage query behavior
- REST API URL encoding requirements

## References

- [OData v3 Specification](https://www.odata.org/documentation/odata-version-3-0/)
- [Azure Table Storage Query Documentation](https://learn.microsoft.com/en-us/rest/api/storageservices/querying-tables-and-entities)
- [EBNF Standard (ISO/IEC 14977)](https://www.iso.org/standard/26153.html)

---

**Version:** 1.0  
**Last Updated:** December 2025  
**Maintainer:** LocalZure Team
