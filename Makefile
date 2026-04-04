.PHONY: install lint format test test-unit test-integration test-service clean check

install:
	uv pip install --system -e ".[dev]"
	uv pip install --system -e libs/
	pre-commit install

lint:
	ruff check .
	mypy libs/fpl_lib/ --ignore-missing-imports

format:
	ruff check --fix .
	ruff format .

test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

test-service:
	@echo "Usage: make test-service SERVICE=data"
	cd services/$(SERVICE) && pytest

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +

check: lint test
