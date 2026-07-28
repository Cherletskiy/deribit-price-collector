PYTHON := uv run

.PHONY: setup format lint typecheck test check

setup:
	uv sync --group dev

format:
	$(PYTHON) ruff format .

lint:
	$(PYTHON) ruff check .

typecheck:
	$(PYTHON) mypy

test:
	$(PYTHON) pytest --cov

check:
	$(PYTHON) ruff format --check .
	$(PYTHON) ruff check .
	$(PYTHON) mypy
	$(PYTHON) pytest --cov
