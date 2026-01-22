from itertools import islice
from typing import Iterable

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
        f"Dispatching price fetch tasks | tickers_total: {len(config.TICKERS)} | batch_size: {batch_size}"
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
    Обработка одного батча тикеров с частичным успехом:
    ошибка при обработке одного тикера не прерывает обработку остальных.
    """
    logger.debug(f"Starting price batch | tickers: {tickers}")

    client = SyncDeribitClient()
    session = SyncSessionLocal()
    success_count = 0
    failed_tickers = []

    try:
        repo = SyncPriceRepository(session)

        for ticker in tickers:
            try:
                price, timestamp = client.get_index_price_time(ticker)
                repo.save_price(ticker=ticker, price=price, timestamp=timestamp)
                success_count += 1
                logger.debug(f"Saved price for {ticker}: {price} at {timestamp}")
            except Exception as e:
                failed_tickers.append(ticker)
                logger.error(f"Failed to process ticker '{ticker}': {e}")

        if success_count > 0:
            session.commit()
            logger.info(
                f"Price batch partially/completely succeeded | "
                f"success: {success_count}, failed: {len(failed_tickers)} | "
                f"failed_tickers: {failed_tickers}"
            )
        else:
            session.rollback()
            logger.warning(f"All tickers in batch failed: {tickers}")
            raise Exception(f"All tickers failed: {failed_tickers}")

    except Exception:
        logger.exception(f"Price batch failed completely | tickers: {tickers}")
        raise

    finally:
        session.close()
