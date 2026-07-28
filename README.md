# Deribit Price Collector

`deribit-price-collector` is a market data ingestion service that collects index
prices from Deribit, stores an idempotent history in PostgreSQL, and exposes an
HTTP API for querying raw prices, candle aggregations, and summary analytics.

The project started as a learning exercise and was refactored into a stronger
portfolio case focused on reliability, observability, and extensibility.

## Highlights

- Idempotent price ingestion with unique `(ticker, timestamp)` protection
- Batch-based Celery collection with selective retries and backoff
- Historical backfill workflow for data repair
- Reconciliation workflow for stale or missing intervals
- Provider abstraction for future multi-exchange support
- Structured API errors with request IDs
- Runtime health, readiness, JSON metrics, and Prometheus-compatible metrics
- Candle and summary analytics endpoints
- Dockerized local environment with PostgreSQL, Redis, API, worker, and beat
- `uv`-based project setup with `ruff`, `mypy`, `pytest`, and CI checks

## Stack

- Python 3.12
- FastAPI
- Celery
- PostgreSQL
- Redis
- SQLAlchemy 2
- Alembic
- httpx
- Docker Compose
- pytest
- Ruff
- mypy
- uv

## Architecture

The service is split into two execution paths:

### API layer

- async FastAPI application
- async SQLAlchemy access
- read-focused endpoints for historical and analytical queries

### Collector layer

- sync Celery workers
- batch dispatch for instruments
- provider-based market data client abstraction
- retry-aware live collection, backfill, and reconciliation workflows

## Key capabilities

### Ingestion

- periodic live price collection
- idempotent writes on repeated timestamps
- partial batch success handling
- transient vs permanent collector failures

### Repair workflows

- manual backfill CLI for historical repair
- scheduled reconciliation for stale or gapped recent history

### Query APIs

- latest price
- paginated historical prices
- date-range filtering
- candle aggregation
- summary and trend analytics

### Observability

- `GET /api/v1/healthz`
- `GET /api/v1/readyz`
- `GET /api/v1/metrics`
- `GET /api/v1/metrics/prometheus`
- request ID propagation via `X-Request-ID`

## Project layout

```text
.
├── app/
│   ├── api/
│   ├── core/
│   ├── models.py
│   ├── repositories.py
│   ├── schemas.py
│   └── services.py
├── collector/
│   ├── backfill.py
│   ├── client.py
│   ├── exceptions.py
│   ├── providers.py
│   ├── reconcile.py
│   └── tasks.py
├── alembic/
├── tests/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── .env.example
```

## Quick start

### 1. Create the environment file

```bash
cp .env.example .env
```

### 2. Start the local stack

```bash
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- PostgreSQL
- Redis
- Celery worker
- Celery beat

## Local development

### Install dependencies

```bash
uv sync --group dev
```

### Quality checks

```bash
make format
make lint
make typecheck
make test
make check
```

## Environment variables

### Core runtime

```ini
DB_HOST=db
DB_PORT=5432
DB_NAME=deribit_db
DB_USER=postgres
DB_PASSWORD=postgres

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

### Provider and ingestion

```ini
MARKET_DATA_PROVIDER=deribit
DERIBIT_API_BASE_URL=https://www.deribit.com/api/v2
DERIBIT_API_TIMEOUT_SEC=10
PRICE_FETCH_INTERVAL_SEC=60
PRICE_BATCH_SIZE=5
TICKERS=["btc_usd","eth_usd"]
```

### Reconciliation

```ini
RECONCILIATION_INTERVAL_SEC=300
RECONCILIATION_LOOKBACK_SEC=86400
RECONCILIATION_STALE_MULTIPLIER=2
```

### Logging

```ini
LOG_LEVEL=INFO
LOG_JSON=false
```

## HTTP API

Base URL:

```text
http://localhost:8000/api/v1
```

### Operational endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `GET /metrics/prometheus`

### Metadata endpoints

- `GET /instruments`
- `GET /instruments/details`
- `GET /providers`
- `GET /providers/active`

### Market data endpoints

- `GET /prices`
- `GET /prices/latest`
- `GET /prices/by-date`
- `GET /prices/candles`
- `GET /prices/summary`

### Example requests

```bash
curl "http://localhost:8000/api/v1/prices?ticker=btc_usd&limit=10&sorting=desc"
curl "http://localhost:8000/api/v1/prices/latest?ticker=eth_usd"
curl "http://localhost:8000/api/v1/prices/by-date?ticker=btc_usd&timestamp_from=1700000000&timestamp_to=1700003600"
curl "http://localhost:8000/api/v1/prices/candles?ticker=btc_usd&interval=1h&timestamp_from=1700000000&timestamp_to=1700086400"
curl "http://localhost:8000/api/v1/prices/summary?ticker=btc_usd&timestamp_from=1700000000&timestamp_to=1700086400"
curl "http://localhost:8000/api/v1/providers/active"
curl "http://localhost:8000/api/v1/metrics/prometheus"
```

## Background workflows

### Live collection

- `collector.tasks.dispatch_price_batches`
- `collector.tasks.fetch_price_batch`

### Historical repair

```bash
make backfill RANGE=1d
```

or

```bash
uv run -m collector.backfill --range 1d --ticker btc_usd
```

### Recent reconciliation

```bash
make reconcile LOOKBACK_SECONDS=86400
```

or

```bash
uv run -m collector.reconcile --lookback-seconds 86400 --ticker btc_usd
```

## Error model

Validation and application errors use a consistent response shape:

```json
{
  "error_code": "validation_error",
  "message": "Validation failed",
  "request_id": "a1b2c3d4",
  "details": []
}
```

Every response also includes an `X-Request-ID` header.

## Quality and testing

The project includes:

- endpoint tests
- collector task tests
- repository integration tests
- static typing with mypy
- linting and formatting with Ruff

Typical commands:

```bash
uv run pytest
uv run ruff check .
uv run mypy .
```

## Why this project is stronger than a basic pet project

This codebase is intentionally positioned as a small but production-oriented
data service rather than a CRUD demo. The main focus areas are:

- reliability under retries and repeated collection
- recoverability through backfill and reconciliation
- clear API contracts and operational visibility
- architecture that can grow from one provider to multiple exchanges

## Next steps

Potential future upgrades:

- additional market data providers
- database-side analytical aggregations
- Prometheus/Grafana dashboards
- reconciliation outcome counters and alerts
- full end-to-end integration environment
