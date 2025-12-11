# LocalZure Documentation

Welcome to the LocalZure documentation! This guide will help you find the information you need.

## 📚 Documentation Structure

### Quick Start
- **[Quickstart Guide](guides/QUICKSTART.md)** - Get up and running in 5 minutes
- **[Cheat Sheet](guides/CHEATSHEET.md)** - Quick reference for common commands
- **[Docker Guide](guides/DOCKER.md)** - Running LocalZure in containers

### Services Documentation

#### Service Bus
- **[Service Bus Overview](services/servicebus/README.md)** - Complete Service Bus documentation
- **[Architecture](services/servicebus/architecture.md)** - Technical architecture and design
- **[Persistence Guide](services/servicebus/persistence.md)** - Storage backends and configuration
- **[Performance](services/servicebus/performance.md)** - Performance tuning and benchmarks
- **[Filters](services/servicebus/filters.md)** - SQL filter syntax and examples
- **[Operations](services/servicebus/operations.md)** - Operational procedures
- **[Troubleshooting](services/servicebus/troubleshooting.md)** - Common issues and solutions
- **[Compatibility](services/servicebus/compatibility.md)** - Azure Service Bus compatibility
- **[Logging](services/servicebus/logging.md)** - Logging and observability

#### Blob Storage
- **[Container API](services/blob-storage/container-api.md)** - Blob container operations

#### Table Storage
- **[Table Storage Docs](table-storage/)** - Table storage documentation

### Developer Guides
- **[Contributing Guide](guides/CONTRIBUTING.md)** - How to contribute to LocalZure
- **[Persistence Quick Reference](guides/PERSISTENCE-QUICKREF.md)** - Quick guide for persistence features

### Reference Documentation
- **[Architecture](reference/architecture.md)** - Overall system architecture
- **[Integration Guide](reference/INTEGRATION.md)** - Integrating with LocalZure
- **[Status & Roadmap](reference/STATUS.md)** - Current status and future plans
- **[Release Checklist](reference/RELEASE_CHECKLIST.md)** - Release process
- **[Completion Criteria](reference/COMPLETE.md)** - Definition of done

### Implementation Details
- **[Story Implementations](implementation/)** - Detailed implementation stories
- **[Story Summaries](summaries/)** - Summary reports for completed stories

## 🚀 Getting Started

1. **New to LocalZure?** Start with the [Quickstart Guide](guides/QUICKSTART.md)
2. **Using Service Bus?** Check the [Service Bus Overview](services/servicebus/README.md)
3. **Need persistence?** See the [Persistence Guide](services/servicebus/persistence.md)
4. **Want to contribute?** Read the [Contributing Guide](guides/CONTRIBUTING.md)

## 📖 Common Tasks

### Running LocalZure
```bash
# Start LocalZure
localzure start

# With configuration
localzure start --config config.yaml

# Check status
localzure status
```

### Using Service Bus
```bash
# Create a queue
curl -X PUT http://localhost:7071/servicebus/queues/myqueue

# Send a message
curl -X POST http://localhost:7071/servicebus/queues/myqueue/messages \
  -d '{"body": "Hello World"}'
```

### Managing Storage
```bash
# View storage stats
localzure storage stats

# Export data
localzure storage export backup.json

# Import data
localzure storage import-data backup.json
```

## 🔍 Finding Documentation

### By Topic
- **Installation & Setup**: [Quickstart](guides/QUICKSTART.md), [Docker](guides/DOCKER.md)
- **Service Bus Features**: [Service Bus Docs](services/servicebus/)
- **Persistence & Storage**: [Persistence Guide](services/servicebus/persistence.md)
- **Development**: [Contributing](guides/CONTRIBUTING.md), [Architecture](reference/architecture.md)
- **Operations**: [Operations Guide](services/servicebus/operations.md)
- **Troubleshooting**: [Troubleshooting Guide](services/servicebus/troubleshooting.md)

### By Audience
- **Users**: Start with [Quickstart](guides/QUICKSTART.md)
- **Developers**: See [Contributing](guides/CONTRIBUTING.md) and [Architecture](reference/architecture.md)
- **Operators**: Check [Operations](services/servicebus/operations.md) and [Docker](guides/DOCKER.md)

## 📊 Documentation Status

| Service | Status | Completeness |
|---------|--------|-------------|
| Service Bus | ✅ Complete | 95% |
| Blob Storage | 🚧 In Progress | 30% |
| Table Storage | 🚧 In Progress | 20% |

## 🤝 Contributing to Documentation

Found an issue or want to improve the docs? See our [Contributing Guide](guides/CONTRIBUTING.md).

### Documentation Standards
- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Keep up-to-date with code changes
- Follow Markdown best practices

## 📝 Recent Updates

- **Dec 11, 2025**: Added persistence layer documentation (SVC-SB-010)
- **Dec 8, 2025**: Comprehensive Service Bus documentation (SVC-SB-009)
- **Dec 5, 2025**: Initial documentation structure

## 🔗 External Resources

- **GitHub Repository**: https://github.com/oladejiayo/localzure
- **Azure Service Bus Docs**: https://docs.microsoft.com/azure/service-bus-messaging/
- **Azure Storage Docs**: https://docs.microsoft.com/azure/storage/

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/oladejiayo/localzure/issues)
- **Discussions**: [GitHub Discussions](https://github.com/oladejiayo/localzure/discussions)

---

**Last Updated**: December 11, 2025  
**Version**: 0.2.0
