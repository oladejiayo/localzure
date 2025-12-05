# LocalZure Dockerfile
# Build: docker build -t localzure/localzure:latest .
# Run: docker run -p 7071:7071 localzure/localzure:latest

FROM python:3.11-slim

LABEL maintainer="LocalZure Contributors"
LABEL description="Local Azure Cloud Platform Emulator"
LABEL version="0.1.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose default port
EXPOSE 7071

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7071/health || exit 1

# Set environment variables
ENV LOCALZURE_HOST=0.0.0.0
ENV LOCALZURE_PORT=7071
ENV LOCALZURE_LOG_LEVEL=INFO

# Run LocalZure
CMD ["sh", "-c", "localzure start --host ${LOCALZURE_HOST} --port ${LOCALZURE_PORT} --log-level ${LOCALZURE_LOG_LEVEL}"]
