# PDFMathTranslate Makefile

.PHONY: help install dev api gradio build build-api build-gradio up down logs clean test

# Default target
help:
	@echo "PDFMathTranslate Development Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies"
	@echo "  dev         Install in development mode"
	@echo ""
	@echo "Run locally:"
	@echo "  api         Start API server"
	@echo "  gradio      Start Gradio interface"
	@echo ""
	@echo "Docker:"
	@echo "  build       Build all Docker images"
	@echo "  build-api   Build API server image"
	@echo "  build-gradio Build Gradio interface image"
	@echo "  up          Start all services with docker-compose"
	@echo "  down        Stop all services"
	@echo "  logs        Show docker-compose logs"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean       Clean up temporary files"
	@echo "  test        Run tests"

# Setup commands
install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install

# Run locally
api:
	python api_server.py

gradio:
	pdf2zh --gui

# Docker commands
build: build-api build-gradio

build-api:
	docker build -f Dockerfile.api -t pdf2zh-api .

build-gradio:
	docker build -f Dockerfile -t pdf2zh-gradio .

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Development commands
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/ 2>/dev/null || true
	rm -rf pdf2zh_files/* 2>/dev/null || true

test:
	pytest tests/ -v

# Production commands
prod-up:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Health checks
health-api:
	curl -f http://localhost:8000/api/health || echo "API server not responding"

health-gradio:
	curl -f http://localhost:7860 || echo "Gradio server not responding"

# Quick development setup
setup-dev: dev
	mkdir -p pdf2zh_files static config
	@echo "Development environment ready!"
	@echo "Run 'make api' to start the API server"
	@echo "Run 'make gradio' to start the Gradio interface"

# Container management
restart:
	docker-compose restart

rebuild: down clean build up

# Monitoring
status:
	docker-compose ps
	@echo ""
	@echo "Service Health:"
	@make health-api
	@make health-gradio