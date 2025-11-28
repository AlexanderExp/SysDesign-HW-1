.PHONY: help test test-fast test-integration test-billing test-coverage test-watch setup-test clean-test

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

setup-test:
	pip install -r tests/requirements.txt

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -m "not slow"

test-integration:
	pytest tests/ -v -m integration

test-billing:
	pytest tests/ -v -m billing

test-coverage:
	pytest tests/ -v --cov=services --cov-report=html --cov-report=term

test-watch:
	pytest-watch tests/ -v

clean-test:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

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
	pytest tests/ -v --cov=services --cov-report=xml