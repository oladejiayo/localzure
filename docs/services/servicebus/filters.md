# Service Bus Filter Syntax Guide

Complete guide to SQL Filters and Correlation Filters for topic subscriptions in LocalZure Service Bus.

## Overview

Filters allow subscriptions to selectively receive messages from a topic based on message properties. LocalZure supports two types of filters:

1. **SQL Filters** - Flexible, SQL-like expressions for complex filtering
2. **Correlation Filters** - Fast, property-based matching for simple scenarios

## SQL Filters

### Supported Syntax

LocalZure implements a SQL92 subset compatible with Azure Service Bus:

**Comparison Operators:**
- `=` - Equal
- `!=` or `<>` - Not equal
- `<` - Less than
- `>` - Greater than
- `<=` - Less than or equal
- `>=` - Greater than or equal

**Logical Operators:**
- `AND` - Logical AND
- `OR` - Logical OR
- `NOT` - Logical NOT

**Set Membership:**
- `IN ('value1', 'value2', ...)` - Value in list
- `NOT IN ('value1', 'value2', ...)` - Value not in list

**Pattern Matching:**
- `LIKE 'pattern%'` - Wildcard matching (% = any characters)
- `NOT LIKE 'pattern%'` - Negative wildcard matching

**Null Checking:**
- `IS NULL` - Value is null
- `IS NOT NULL` - Value is not null

### System Properties

Access message system properties with `sys.` prefix:

- `sys.MessageId` - Message identifier
- `sys.Label` - Message label
- `sys.ContentType` - Content type
- `sys.CorrelationId` - Correlation identifier
- `sys.SessionId` - Session identifier
- `sys.ReplyTo` - Reply-to address
- `sys.To` - Destination address
- `sys.DeliveryCount` - Number of delivery attempts
- `sys.EnqueuedTimeUtc` - Enqueue timestamp
- `sys.SequenceNumber` - Sequence number

### User Properties

Access custom message properties directly by name:

```sql
priority = 'high'
customer_tier != 'free'
quantity > 100
```

**Supported Types:**
- String (single quotes): `'value'`
- Integer: `42`, `-100`
- Float: `3.14`, `-0.5`
- Boolean: `true`, `false`

### Examples

#### Simple Property Match

```sql
priority = 'high'
```

Matches messages where user property `priority` equals `'high'`.

#### Multiple Conditions (AND)

```sql
sys.Label = 'order' AND quantity > 100
```

Matches order messages with quantity greater than 100.

#### Multiple Conditions (OR)

```sql
priority = 'urgent' OR sys.Label = 'alert'
```

Matches urgent messages OR alert messages.

#### Set Membership

```sql
color IN ('red', 'blue', 'green')
```

Matches messages where color is red, blue, or green.

#### Pattern Matching

```sql
sys.MessageId LIKE 'order-%'
```

Matches messages with IDs starting with "order-".

#### Complex Expression

```sql
(priority = 'high' OR customer_tier = 'premium') 
AND region = 'us-west' 
AND quantity > 50
```

Matches high-priority or premium customer orders in us-west with quantity > 50.

#### Null Checking

```sql
discount IS NOT NULL AND discount > 0
```

Matches messages with a non-null positive discount.

#### Negation

```sql
NOT (status = 'cancelled' OR status = 'expired')
```

Matches messages that are neither cancelled nor expired.

### Filter Performance

**Fast Operations** (< 0.1ms):
- Equality: `property = 'value'`
- Comparison: `quantity > 100`
- Set membership: `status IN ('active', 'pending')`

**Moderate Operations** (< 1ms):
- Multiple conditions: `a = 1 AND b = 2 AND c = 3`
- Pattern matching: `id LIKE 'order-%'`

**Complex Operations** (< 5ms):
- Many nested conditions: `(a AND (b OR (c AND d)))`
- Multiple patterns: `id LIKE 'A%' OR id LIKE 'B%'`

**Best Practices:**
- Keep expressions simple (< 5 conditions)
- Use correlation filters for exact matches (10x faster)
- Avoid complex nesting
- Use indexed properties when possible

## Correlation Filters

### Overview

Correlation filters match exact values on specific properties. They are optimized for performance and should be preferred over SQL filters when possible.

**Performance:** ~10x faster than SQL filters (< 0.01ms)

### Syntax

Correlation filters are defined as JSON objects:

```json
{
  "CorrelationId": "order-12345",
  "Label": "order.created",
  "Properties": {
    "customer_tier": "premium",
    "region": "us-east"
  }
}
```

### Matching Logic

ALL specified properties must match (implicit AND logic):

```json
{
  "Label": "order",
  "Properties": {
    "priority": "high",
    "region": "us-west"
  }
}
```

This matches messages where:
- Label = "order" **AND**
- priority = "high" **AND**
- region = "us-west"

### System Property Mapping

| Correlation Filter Property | Message System Property |
|----------------------------|------------------------|
| `CorrelationId` | `sys.CorrelationId` |
| `Label` | `sys.Label` |
| `MessageId` | `sys.MessageId` |
| `ReplyTo` | `sys.ReplyTo` |
| `SessionId` | `sys.SessionId` |
| `To` | `sys.To` |
| `ContentType` | `sys.ContentType` |

### Examples

#### Match by Correlation ID

```json
{
  "CorrelationId": "request-789"
}
```

Matches messages with correlation ID "request-789".

#### Match by Label and Property

```json
{
  "Label": "order.created",
  "Properties": {
    "customer_type": "enterprise"
  }
}
```

Matches order.created messages from enterprise customers.

#### Match Multiple Properties

```json
{
  "Properties": {
    "priority": "high",
    "category": "electronics",
    "region": "us-east",
    "in_stock": "true"
  }
}
```

Matches high-priority electronics orders in us-east that are in stock.

#### Request-Reply Pattern

```json
{
  "CorrelationId": "request-12345",
  "Label": "response"
}
```

Matches response messages for request-12345.

## Choosing Between SQL and Correlation Filters

| Use Case | Recommended Filter | Reason |
|----------|-------------------|--------|
| Exact property matches | Correlation | 10x faster |
| Range checks (`>`, `<`) | SQL | Only SQL supports ranges |
| Pattern matching (`LIKE`) | SQL | Only SQL supports patterns |
| OR logic | SQL | Correlation is AND-only |
| Complex conditions | SQL | More flexible |
| High throughput | Correlation | Lower latency |
| Simple routing | Correlation | Simpler syntax |

### Performance Comparison

| Filter Type | Latency (P50) | Throughput |
|-------------|---------------|------------|
| Correlation Filter | < 0.01ms | 100,000 msg/s |
| Simple SQL Filter (1-2 conditions) | < 0.1ms | 50,000 msg/s |
| Complex SQL Filter (5+ conditions) | < 1ms | 10,000 msg/s |

## Creating Filters via API

### SQL Filter

```python
import requests

# Create subscription with SQL filter
response = requests.put(
    "http://localhost:8000/servicebus/topics/orders/subscriptions/high-priority/rules/sql-rule",
    headers={"Content-Type": "application/xml"},
    data='''
    <entry xmlns="http://www.w3.org/2005/Atom">
      <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
          <Filter>
            <SqlExpression>priority = 'high' AND quantity > 100</SqlExpression>
          </Filter>
        </RuleDescription>
      </content>
    </entry>
    '''
)
```

### Correlation Filter

```python
import requests

# Create subscription with correlation filter
response = requests.put(
    "http://localhost:8000/servicebus/topics/orders/subscriptions/premium-customers/rules/correlation-rule",
    headers={"Content-Type": "application/xml"},
    data='''
    <entry xmlns="http://www.w3.org/2005/Atom">
      <content type="application/xml">
        <RuleDescription xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
          <Filter>
            <CorrelationId>order-12345</CorrelationId>
            <Label>order.created</Label>
            <Properties>
              <customer_tier>premium</customer_tier>
              <region>us-east</region>
            </Properties>
          </Filter>
        </RuleDescription>
      </content>
    </entry>
    '''
)
```

## Filter Evaluation Details

### Evaluation Order

1. **Default Rule**: If present, always matches (catches all messages)
2. **Custom Rules**: Evaluated in creation order
3. **First Match**: Message routed if ANY rule matches (OR logic across rules)

### Filter Limits

| Limit | Value | Azure Comparison |
|-------|-------|------------------|
| Max Rules per Subscription | 100 | 100 |
| Max SQL Expression Length | 1024 chars | 1024 chars |
| Max Correlation Properties | 10 | 10 |
| Max Property Name Length | 128 chars | 128 chars |
| Max Property Value Length | 256 chars | 256 chars |

### Type Coercion

LocalZure performs automatic type coercion for comparisons:

```sql
-- String to number
quantity > '100'  -- '100' coerced to 100

-- Number to string  
'100' = quantity  -- 100 coerced to '100'

-- Boolean to string
active = 'true'   -- 'true' coerced to true
```

**Best Practice:** Use correct types to avoid coercion overhead.

## Common Filter Patterns

### Regional Routing

```sql
-- SQL Filter
region = 'us-west' OR region = 'us-east'

-- Correlation Filter
{
  "Properties": {
    "region": "us-west"
  }
}
```

### Priority-Based Routing

```sql
-- High priority
priority = 'high' OR priority = 'urgent'

-- Low priority  
priority NOT IN ('high', 'urgent', 'critical')
```

### Customer Tier Routing

```sql
-- Premium customers
customer_tier = 'premium' OR customer_tier = 'enterprise'

-- Free tier (use default rule or SQL)
customer_tier = 'free' OR customer_tier IS NULL
```

### Content Type Routing

```sql
-- JSON messages
sys.ContentType = 'application/json'

-- XML messages
sys.ContentType = 'application/xml' OR sys.ContentType = 'text/xml'
```

### Time-Based Routing

```sql
-- Recent messages (last 5 minutes)
sys.EnqueuedTimeUtc >= '2025-12-08T12:00:00Z'

-- Older messages
sys.EnqueuedTimeUtc < '2025-12-08T12:00:00Z'
```

### Retry Routing

```sql
-- Failed messages (delivery count > 3)
sys.DeliveryCount > 3

-- First attempt
sys.DeliveryCount = 1
```

## Troubleshooting Filters

### No Messages Received

**Problem:** Subscription receives no messages despite messages sent to topic.

**Solutions:**
1. Check filter expression syntax:
   ```bash
   # View subscription rules
   curl http://localhost:8000/servicebus/topics/mytopic/subscriptions/mysub/rules
   ```

2. Test message properties match filter:
   ```python
   # Send with required properties
   message = ServiceBusMessage(
       "test",
       application_properties={"priority": "high", "region": "us-west"}
   )
   ```

3. Check for typos in property names (case-sensitive)

4. Verify data types match (string vs number)

### Filter Syntax Errors

**Problem:** Error creating filter rule.

**Solutions:**
1. Validate SQL syntax:
   - Use single quotes for strings: `'value'` not `"value"`
   - Check operator spelling: `AND` not `and`
   - Match parentheses: `(a OR b) AND c`

2. Check property names:
   - No special characters except underscore
   - Case-sensitive
   - Max 128 characters

3. Verify correlation filter structure:
   - Valid JSON format
   - Property names match message properties
   - All values are strings

### Performance Issues

**Problem:** High latency with filters.

**Solutions:**
1. Simplify SQL expressions (< 5 conditions)
2. Use correlation filters for exact matches
3. Avoid complex pattern matching (`LIKE` with many wildcards)
4. Reduce number of rules per subscription

## References

- **Azure Service Bus Filters**: https://docs.microsoft.com/azure/service-bus-messaging/topic-filters
- **SQL Filter Grammar**: https://docs.microsoft.com/azure/service-bus-messaging/service-bus-messaging-sql-filter
- **Filter Performance**: See [Performance Tuning Guide](servicebus-performance.md)

## Next Steps

- **[Architecture Guide](servicebus-architecture.md)** - Understanding filter evaluation engine
- **[Performance Tuning](servicebus-performance.md)** - Optimizing filter performance
- **[Examples](../examples/)** - Complete filter examples in multiple languages
