.PHONY: help test test-fast test-integration test-billing test-coverage test-watch setup-test clean-test lint format

help:
	@echo "Available commands:"
	@echo "  make test              - Run all tests"
	@echo "  make test-fast         - Run fast tests only (skip slow)"
	@echo "  make test-integration  - Run integration tests"
	@echo "  make test-billing      - Run billing tests"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-watch        - Run tests in watch mode"
	@echo "  make setup-test        - Install test dependencies"
	@echo "  make clean-test        - Clean test artifacts"
	@echo "  make lint              - Run linter checks"
	@echo "  make format            - Format code"
	@echo "  make up                - Start Docker services"
	@echo "  make down              - Stop Docker services"
	@echo "  make logs              - Show Docker logs"
	@echo "  make restart           - Restart rental-core and billing-worker"
	@echo "  make test-all          - Start services, run tests, stop services"
	@echo "  make test-ci           - Run CI test workflow"
	@echo "  make migrate-rental    - Run rental database migrations"
	@echo "  make migrate-billing   - Run billing database migrations"
	@echo "  make migrate-all       - Run all database migrations"

setup-test:
	uv sync

test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -v -m "not slow"

test-integration:
	uv run pytest tests/ -v -m integration

test-billing:
	uv run pytest tests/ -v -m billing

test-coverage:
	uv run pytest tests/ -v --cov=services --cov-report=html --cov-report=term

test-watch:
	uv run pytest-watch tests/ -v

clean-test:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

# Linting and formatting
lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# Docker commands
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart rental-core billing-worker

# Combined workflow
test-all: up
	@echo "Waiting for services to be ready..."
	@sleep 5
	@make test
	@make down

test-ci: up
	@echo "Waiting for services to be ready..."
	@sleep 10
	uv run pytest tests/ -v --cov=services --cov-report=xml

migrate-rental:
	uv run alembic -c alembic_rental.ini upgrade head

migrate-billing:
	uv run alembic -c alembic_billing.ini upgrade head

migrate-all: migrate-rental migrate-billing
