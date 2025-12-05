# Examples Directory

This directory contains example configurations and demo applications for LocalZure.

## Configuration Examples

### config.example.yaml

Example YAML configuration file showing all available options:

```bash
# Copy and customize
cp examples/config.example.yaml config.yaml
localzure start --config config.yaml
```

### .env.example

Example environment variables for Azure SDK integration:

```bash
# Copy and customize
cp examples/.env.example .env
# Load in your shell or application
```

## Demo Applications

### test_servicebus.py

Comprehensive Service Bus demo showing:
- Queue creation and management
- Message send/receive operations
- Topic and subscription patterns
- Error handling
- Health checks

**Usage:**

```bash
# Start LocalZure first
localzure start

# Run the demo
python examples/test_servicebus.py
```

## Adding Examples

When adding new examples:

1. Create well-documented code
2. Include comments explaining each step
3. Add error handling
4. Update this README
5. Test thoroughly before committing
