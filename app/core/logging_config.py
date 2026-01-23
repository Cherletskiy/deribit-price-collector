import logging
from logging.handlers import RotatingFileHandler

from app.core.config import config


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    level = logging.getLevelName(config.LOG_LEVEL.upper())
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Обработчик для вывода в терминал
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # Обработчик для записи в файл с ротацией
        file_handler = RotatingFileHandler(
            "app.log", maxBytes=10_000_000, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
