from collections import Counter
from threading import Lock


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
