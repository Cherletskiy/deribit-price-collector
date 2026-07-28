from collections import Counter
from collections.abc import Mapping
from decimal import Decimal
from threading import Lock
from time import time
from typing import Protocol


class PriceSnapshot(Protocol):
    price: Decimal
    timestamp: int


def build_business_metrics_snapshot(
    total_prices: int,
    counts_by_ticker: dict[str, int],
    latest_prices_by_ticker: Mapping[str, PriceSnapshot],
) -> dict[str, object]:
    now_timestamp = int(time())
    latest_prices: dict[str, dict[str, object]] = {}

    for ticker, price_entry in latest_prices_by_ticker.items():
        latest_timestamp = int(price_entry.timestamp)
        latest_prices[ticker] = {
            "price": str(price_entry.price),
            "timestamp": latest_timestamp,
            "freshness_seconds": max(now_timestamp - latest_timestamp, 0),
        }

    return {
        "total_prices": total_prices,
        "counts_by_ticker": counts_by_ticker,
        "latest_prices": latest_prices,
    }


def business_snapshot_to_prometheus(snapshot: dict[str, object]) -> str:
    total_prices_value = snapshot.get("total_prices", 0)
    total_prices = int(total_prices_value) if isinstance(total_prices_value, int) else 0
    lines = [
        "# HELP app_prices_stored_total Total number of stored price points.",
        "# TYPE app_prices_stored_total gauge",
        f"app_prices_stored_total {total_prices}",
    ]

    counts_by_ticker = snapshot["counts_by_ticker"]
    if isinstance(counts_by_ticker, dict):
        for ticker, count in sorted(counts_by_ticker.items()):
            lines.append(f'app_price_points_total{{ticker="{ticker}"}} {int(count)}')

    latest_prices = snapshot["latest_prices"]
    if isinstance(latest_prices, dict):
        for ticker, payload in sorted(latest_prices.items()):
            if not isinstance(payload, dict):
                continue
            price = payload.get("price", "0")
            timestamp = int(payload.get("timestamp", 0))
            freshness_seconds = int(payload.get("freshness_seconds", 0))
            lines.append(
                f'app_latest_price_value{{ticker="{ticker}"}} {Decimal(str(price))}'
            )
            lines.append(f'app_latest_price_timestamp{{ticker="{ticker}"}} {timestamp}')
            lines.append(
                f'app_data_freshness_seconds{{ticker="{ticker}"}} {freshness_seconds}'
            )

    return "\n".join(lines) + "\n"


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_in_progress = 0
        self._requests_total = 0
        self._requests_failed = 0
        self._path_counts: Counter[str] = Counter()
        self._status_counts: Counter[str] = Counter()
        self._request_durations_ms_total = 0.0

    def on_request_start(self, path: str) -> None:
        with self._lock:
            self._requests_in_progress += 1
            self._path_counts[path] += 1

    def on_request_end(self, path: str, status_code: int, duration_ms: float) -> None:
        status_group = f"{status_code // 100}xx"
        with self._lock:
            self._requests_in_progress -= 1
            self._requests_total += 1
            self._status_counts[status_group] += 1
            self._request_durations_ms_total += duration_ms
            if status_code >= 400:
                self._requests_failed += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            average_duration_ms = 0.0
            if self._requests_total > 0:
                average_duration_ms = (
                    self._request_durations_ms_total / self._requests_total
                )

            return {
                "requests_in_progress": self._requests_in_progress,
                "requests_total": self._requests_total,
                "requests_failed": self._requests_failed,
                "average_request_duration_ms": round(average_duration_ms, 2),
                "path_counts": dict(self._path_counts),
                "status_counts": dict(self._status_counts),
            }

    def to_prometheus(self) -> str:
        with self._lock:
            lines = [
                (
                    "# HELP app_requests_in_progress "
                    "Current number of in-progress HTTP requests."
                ),
                "# TYPE app_requests_in_progress gauge",
                f"app_requests_in_progress {self._requests_in_progress}",
                ("# HELP app_requests_total Total number of completed HTTP requests."),
                "# TYPE app_requests_total counter",
                f"app_requests_total {self._requests_total}",
                (
                    "# HELP app_requests_failed_total "
                    "Total number of failed HTTP requests."
                ),
                "# TYPE app_requests_failed_total counter",
                f"app_requests_failed_total {self._requests_failed}",
                (
                    "# HELP app_request_duration_ms_total "
                    "Total HTTP request processing time in milliseconds."
                ),
                "# TYPE app_request_duration_ms_total counter",
                f"app_request_duration_ms_total {self._request_durations_ms_total:.2f}",
            ]

            for path, count in sorted(self._path_counts.items()):
                lines.append(f'app_request_path_total{{path="{path}"}} {count}')

            for status_group, count in sorted(self._status_counts.items()):
                lines.append(
                    f'app_request_status_total{{status_group="{status_group}"}} {count}'
                )

            return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()
