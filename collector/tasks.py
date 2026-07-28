from collections.abc import Iterable
from itertools import islice

import httpx
from celery import Celery

from app.core.config import config
from app.core.db import SyncSessionLocal
from app.core.logging_config import setup_logger
from app.repositories import SyncPriceRepository
from collector.client import SyncDeribitClient
from collector.exceptions import (
    PriceBatchPermanentError,
    PriceBatchTransientError,
    PriceCollectionPermanentError,
    PriceCollectionTransientError,
)

logger = setup_logger(__name__)


def chunked[T](iterable: Iterable[T], size: int) -> Iterable[list[T]]:
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
    autoretry_for=(PriceBatchTransientError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    expires=50,
    name="collector.tasks.fetch_price_batch",
)
def fetch_price_batch(tickers: list[str]) -> None:
    logger.info("Starting price batch | size=%d", len(tickers))

    session = SyncSessionLocal()
    success_count = 0
    permanent_failures: list[tuple[str, str]] = []
    transient_failures: list[tuple[str, str]] = []

    try:
        repo = SyncPriceRepository(session)

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
                except PriceCollectionPermanentError as exc:
                    permanent_failures.append((ticker, str(exc)))
                    logger.error(
                        "Permanent failure processing ticker | ticker=%s | error=%s",
                        ticker,
                        exc,
                    )
                except PriceCollectionTransientError as exc:
                    transient_failures.append((ticker, str(exc)))
                    logger.error(
                        "Transient failure processing ticker | ticker=%s | error=%s",
                        ticker,
                        exc,
                    )

        if success_count > 0:
            try:
                session.commit()
            except Exception as exc:
                session.rollback()
                raise PriceBatchTransientError(
                    f"Failed to commit collected prices: {exc}"
                ) from exc
            logger.info(
                (
                    "Batch completed | success=%d | permanent_failed=%d "
                    "| transient_failed=%d"
                ),
                success_count,
                len(permanent_failures),
                len(transient_failures),
            )
        else:
            session.rollback()
            failed_tickers = [
                ticker for ticker, _ in permanent_failures + transient_failures
            ]
            logger.warning("All tickers failed | tickers=%s", failed_tickers)
            if transient_failures:
                raise PriceBatchTransientError(
                    f"Transient batch failure for tickers: {failed_tickers}"
                )
            raise PriceBatchPermanentError(
                f"Permanent batch failure for tickers: {failed_tickers}"
            )

    except PriceBatchTransientError:
        logger.exception("Batch failed with transient error | tickers=%s", tickers)
        raise
    except PriceBatchPermanentError:
        logger.exception("Batch failed with permanent error | tickers=%s", tickers)
        raise
    except Exception as exc:
        logger.exception("Batch failed | tickers=%s", tickers)
        session.rollback()
        raise PriceBatchTransientError(
            f"Unexpected batch failure for tickers {tickers}: {exc}"
        ) from exc
    finally:
        session.close()
