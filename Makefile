# LocalZure Makefile
# Quick commands for development and deployment

.PHONY: help install dev test coverage lint format clean docker-build docker-run docker-stop start stop

help:
	@echo "LocalZure - Local Azure Cloud Platform Emulator"
	@echo ""
	@echo "Available commands:"
	@echo "  make install       - Install LocalZure in development mode"
	@echo "  make dev           - Start LocalZure in development mode with auto-reload"
	@echo "  make start         - Start LocalZure"
	@echo "  make test          - Run all tests"
	@echo "  make coverage      - Run tests with coverage report"
	@echo "  make lint          - Run code linters"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run LocalZure in Docker"
	@echo "  make docker-stop   - Stop Docker container"

install:
	pip install -e ".[dev]"

dev:
	localzure start --reload --log-level DEBUG

start:
	localzure start

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=localzure --cov-report=html --cov-report=term

lint:
	ruff check localzure/
	mypy localzure/

format:
	black localzure/ tests/
	ruff check --fix localzure/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t localzure/localzure:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f localzure
