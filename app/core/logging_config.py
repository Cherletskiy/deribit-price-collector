import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def setup_logger(name: str) -> logging.Logger:
    formatter: logging.Formatter
    if config.LOG_JSON:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        root_logger.setLevel(logging.getLevelName(config.LOG_LEVEL.upper()))

    logger = logging.getLogger(name)
    level = logging.getLevelName(config.LOG_LEVEL.upper())
    logger.setLevel(level)
    logger.propagate = True
    return logger
