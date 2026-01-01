.PHONY: help install dev lint format typecheck test test-cov clean all check

# Default target
help:
	@echo "Long Horizon Agent - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install    Install production dependencies"
	@echo "  make dev        Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint       Run ruff linter"
	@echo "  make format     Format code with ruff"
	@echo "  make typecheck  Run basedpyright type checker"
	@echo "  make check      Run all checks (lint + typecheck)"
	@echo ""
	@echo "Testing:"
	@echo "  make test       Run tests"
	@echo "  make test-cov   Run tests with coverage report"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean      Remove build artifacts and caches"
	@echo "  make all        Run all checks and tests"

# Install production dependencies
install:
	uv pip install -e .

# Install development dependencies
dev:
	uv pip install -e ".[dev]"

# Run linter
lint:
	uv run ruff check src tests

# Format code
format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# Run type checker
typecheck:
	uv run basedpyright src

# Run all code quality checks
check: lint typecheck

# Run tests
test:
	uv run pytest tests -v

# Run tests with coverage
test-cov:
	uv run pytest tests -v --cov=src --cov-report=term-missing --cov-report=html

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run all checks and tests
all: check test
