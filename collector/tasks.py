from collections.abc import Iterable
from itertools import islice

import httpx
from celery import Celery

from app.core.config import config
from app.core.db import SyncSessionLocal
from app.core.logging_config import setup_logger
from app.repositories import SyncPriceRepository
from collector.client import SyncDeribitClient

logger = setup_logger(__name__)


def chunked(iterable: Iterable[str], size: int) -> Iterable[list[str]]:
    """
    Делит iterable на чанки фиксированного размера.
    """
    it = iter(iterable)
    while batch := list(islice(it, size)):
        yield batch


celery_app = Celery("deribit_collector")
celery_app.conf.update(
    broker_url=config.REDIS_URL,
    result_backend=config.REDIS_URL,
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
)

celery_app.conf.beat_schedule = {
    "fetch-deribit-prices": {
        "task": "collector.tasks.dispatch_price_batches",
        "schedule": config.PRICE_FETCH_INTERVAL_SEC,
    }
}


@celery_app.task(
    name="collector.tasks.dispatch_price_batches",
    expires=50,
)
def dispatch_price_batches() -> None:
    """
    Fan-out задача.
    Разбивает тикеры на батчи и ставит задачи в очередь.
    """
    batch_size = config.PRICE_BATCH_SIZE

    logger.debug(
        "Dispatching price fetch tasks | tickers_total=%d | batch_size=%d",
        len(config.TICKERS),
        batch_size,
    )

    for batch in chunked(config.TICKERS, batch_size):
        fetch_price_batch.delay(batch)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
    expires=50,
    name="collector.tasks.fetch_price_batch",
)
def fetch_price_batch(tickers: list[str]) -> None:
    """
    Обработка одного батча тикеров.
    Использует один HTTP-клиент на весь батч для connection pooling.
    """
    logger.info("Starting price batch | size=%d", len(tickers))

    session = SyncSessionLocal()
    success_count = 0
    failed_tickers = []

    try:
        repo = SyncPriceRepository(session)

        # Один HTTP-клиент на весь batch для connection pooling
        with httpx.Client(timeout=config.DERIBIT_API_TIMEOUT_SEC) as http_client:
            client = SyncDeribitClient(http_client)

            for ticker in tickers:
                try:
                    price, timestamp = client.get_index_price_time(ticker)
                    repo.save_price(ticker=ticker, price=price, timestamp=timestamp)
                    success_count += 1

                    logger.debug(
                        "Saved price | ticker=%s | price=%s | timestamp=%s",
                        ticker,
                        price,
                        timestamp,
                    )

                except Exception as exc:
                    failed_tickers.append((ticker, str(exc)))
                    logger.error(
                        "Failed to process ticker | ticker=%s | error=%s",
                        ticker,
                        exc,
                    )

        # Commit только если есть успешные сохранения
        if success_count > 0:
            session.commit()
            logger.info(
                "Batch completed | success=%d | failed=%d | failed_tickers=%s",
                success_count,
                len(failed_tickers),
                [t[0] for t in failed_tickers],
            )
        else:
            session.rollback()
            logger.warning("All tickers failed | tickers=%s", tickers)
            raise Exception(f"All tickers failed: {[t[0] for t in failed_tickers]}")

    except Exception:
        logger.exception("Batch failed | tickers=%s", tickers)
        raise
    finally:
        session.close()
