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


runtime_metrics = RuntimeMetrics()
