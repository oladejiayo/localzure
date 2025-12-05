# Scripts Directory

This directory contains utility scripts for LocalZure development and setup.

## Available Scripts

### bootstrap.py

Interactive setup wizard for LocalZure. Helps you:
- Check prerequisites
- Install LocalZure
- Configure settings
- Start the service

**Usage:**

```bash
# Interactive setup
python scripts/bootstrap.py

# Quick install without prompts
python scripts/bootstrap.py --quick

# Use Docker
python scripts/bootstrap.py --docker

# Development mode
python scripts/bootstrap.py --dev
```

## Adding New Scripts

When creating utility scripts:

1. Add them to this `scripts/` directory
2. Make them executable with proper shebang (`#!/usr/bin/env python3`)
3. Add documentation here
4. Include help text in the script itself
