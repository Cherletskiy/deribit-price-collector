PYTHON := uv run

.PHONY: setup format lint typecheck test check backfill reconcile

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

backfill:
	$(PYTHON) -m collector.backfill --range $(RANGE)

reconcile:
	$(PYTHON) -m collector.reconcile --lookback-seconds $(LOOKBACK_SECONDS)
