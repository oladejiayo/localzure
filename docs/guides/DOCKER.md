# LocalZure Docker Guide

## Quick Start with Docker

### Using Docker Run

```bash
# Pull and run LocalZure
docker run -d \
  --name localzure \
  -p 7071:7071 \
  localzure/localzure:latest

# Check status
docker ps

# View logs
docker logs -f localzure

# Stop
docker stop localzure
```

### Using Docker Compose

```bash
# Start LocalZure
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Building from Source

```bash
# Build image
docker build -t localzure/localzure:latest .

# Or use make
make docker-build

# Run
make docker-run
```

## Configuration

### Environment Variables

```bash
docker run -d \
  --name localzure \
  -p 7071:7071 \
  -e LOCALZURE_LOG_LEVEL=DEBUG \
  localzure/localzure:latest
```

### Custom Configuration File

```bash
docker run -d \
  --name localzure \
  -p 7071:7071 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  localzure/localzure:latest
```

## Port Mapping

Default ports:
- **7071**: Service Bus and main API endpoint

Map to different host ports:

```bash
docker run -d \
  --name localzure \
  -p 8080:7071 \
  localzure/localzure:latest
```

Then access at: `http://localhost:8080`

## Health Check

```bash
# Check health
curl http://localhost:7071/health

# Or inside container
docker exec localzure curl -f http://localhost:7071/health
```

## Networking

### Connect from Host

```bash
# Access from host machine
curl http://localhost:7071/health
```

### Connect from Another Container

```yaml
# docker-compose.yml
services:
  localzure:
    image: localzure/localzure:latest
    networks:
      - app-network
  
  your-app:
    image: your-app:latest
    environment:
      - SERVICEBUS_ENDPOINT=http://localzure:7071
    networks:
      - app-network
    depends_on:
      - localzure

networks:
  app-network:
    driver: bridge
```

## Persistence (Coming Soon)

To persist data across container restarts:

```bash
docker run -d \
  --name localzure \
  -p 7071:7071 \
  -v localzure-data:/app/data \
  localzure/localzure:latest
```

## Development Mode

Run with auto-reload for development:

```bash
docker run -d \
  --name localzure-dev \
  -p 7071:7071 \
  -v $(pwd)/localzure:/app/localzure \
  -e LOCALZURE_LOG_LEVEL=DEBUG \
  localzure/localzure:latest \
  localzure start --reload --log-level DEBUG
```

## Multi-Architecture Support

Build for multiple architectures:

```bash
# Build for AMD64 and ARM64
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t localzure/localzure:latest \
  --push .
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs localzure

# Check if port is already in use
netstat -an | grep 7071

# Use different port
docker run -d -p 8080:7071 localzure/localzure:latest
```

### Can't connect from host

```bash
# Verify container is running
docker ps | grep localzure

# Check container logs
docker logs localzure

# Verify port mapping
docker port localzure
```

### Performance issues

```bash
# Increase memory limit
docker run -d \
  --name localzure \
  --memory="2g" \
  -p 7071:7071 \
  localzure/localzure:latest
```

## Production Deployment

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml localzure

# Scale service
docker service scale localzure_localzure=3
```

### Using Kubernetes

See [KUBERNETES.md](KUBERNETES.md) for Kubernetes deployment guide.

## CI/CD Integration

### GitHub Actions

```yaml
- name: Start LocalZure
  run: |
    docker run -d \
      --name localzure \
      -p 7071:7071 \
      localzure/localzure:latest
    
    # Wait for health check
    timeout 30 bash -c 'until curl -f http://localhost:7071/health; do sleep 1; done'

- name: Run tests
  run: |
    pytest tests/integration/
  env:
    SERVICEBUS_ENDPOINT: http://localhost:7071
```

### GitLab CI

```yaml
services:
  - name: localzure/localzure:latest
    alias: localzure

variables:
  SERVICEBUS_ENDPOINT: http://localzure:7071
```

## Best Practices

1. **Use specific versions** instead of `latest` in production
2. **Set resource limits** for containers
3. **Use health checks** for orchestration
4. **Mount config files** as read-only
5. **Use Docker networks** for container communication
6. **Enable logging** to external systems
7. **Monitor** container health and metrics

## Examples

See [examples/docker/](examples/docker/) for complete Docker examples with various setups.
