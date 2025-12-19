.PHONY: help install format lint check test test-unit test-integration test-security test-all type-check clean build vm-reset vm-stop vm-status

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make format           - Format code with ruff"
	@echo "  make lint             - Lint code with ruff"
	@echo "  make check            - Run format check and lint"
	@echo "  make test             - Run unit tests"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-security    - Run security tests"
	@echo "  make test-all         - Run all tests"
	@echo "  make type-check       - Run type checking with ty"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make build            - Build package"
	@echo "  make vm-kill-mac      - Delete and the Lima VM (macOS)"

install:
	uv sync --all-extras

format:
	uv run ruff format .

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

check:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest tests/ -v

test-debug:
	uv run pytest --log-cli-level=DEBUG

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

type-check:
	uvx ty check

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	uv build

vm-kill-mac:
	limactl stop pctx-sandbox
	limactl delete pctx-sandbox