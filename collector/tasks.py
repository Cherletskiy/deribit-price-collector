from celery import Celery

from app.core.config import Config
from app.core.db import SyncSessionLocal
from app.core.logging_config import setup_logger
from app.repositories import SyncPriceRepository
from collector.client import SyncDeribitClient


logger = setup_logger(__name__)

TICKERS = ["btc_usd", "eth_usd"]

celery_app = Celery("deribit_collector")
celery_app.conf.update(
    broker_url=Config.REDIS_URL,
    result_backend=Config.REDIS_URL,
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
)

celery_app.conf.beat_schedule = {
    "fetch-deribit-prices": {
        "task": "collector.tasks.fetch_prices_task",
        "schedule": Config.PRICE_FETCH_INTERVAL_SEC,
    }
}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
    name="collector.tasks.fetch_prices_task",
)
def fetch_prices_task(self):
    """
    Синхронная Celery задача для сбора цен.
    """
    logger.info("Starting price collection task")

    client = SyncDeribitClient()
    session = SyncSessionLocal()

    try:
        repo = SyncPriceRepository(session)

        for ticker in TICKERS:
            price, timestamp = client.get_index_price_time(ticker)
            repo.save_price(
                ticker=ticker,
                price=price,
                timestamp=timestamp,
            )

        session.commit()
        logger.info("Price collection task completed successfully")

    except Exception as exc:
        session.rollback()
        logger.exception("Price collection task failed")
        raise

    finally:
        session.close()
        logger.debug("Database session closed")
