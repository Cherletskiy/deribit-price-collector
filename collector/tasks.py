import asyncio
from datetime import datetime, timezone
from typing import List, Literal

from celery import Celery

from app.core.config import Config
from app.core.db import SyncSessionLocal
from app.core.logging_config import setup_logger
from app.repositories import SyncPriceRepository
from collector.client import DeribitClient


logger = setup_logger(__name__)

Ticker = Literal["btc_usd", "eth_usd"]
TICKERS: List[Ticker] = ["btc_usd", "eth_usd"]

celery_app = Celery("deribit_collector")
celery_app.conf.update(
    broker_url=Config.REDIS_URL,
    result_backend=Config.REDIS_URL,
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "fetch-deribit-prices": {
        "task": "collector.tasks.fetch_prices_task",
        "schedule": Config.PRICE_FETCH_INTERVAL_SEC,
    }
}


async def _fetch_prices_async(
    tickers: List[Ticker],
    repo: SyncPriceRepository,
) -> None:
    """
    Асинхронно получает цены из Deribit и сохраняет их в БД.
    """
    async with DeribitClient() as client:
        for ticker in tickers:
            try:
                price, timestamp = await client.get_index_price_time(ticker)

                repo.save_price(
                    ticker=ticker,
                    price=price,
                    timestamp=timestamp,
                )
            except Exception as e:
                logger.error(f"Failed to fetch price for {ticker}: {e}")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
    name="collector.tasks.fetch_prices_task",
)
def fetch_prices_task(self) -> None:
    """
    ...
    """
    logger.info("Starting price collection task")

    with SyncSessionLocal() as session:
        repo = SyncPriceRepository(session)

        try:
            asyncio.run(_fetch_prices_async(TICKERS, repo))
            session.commit()
            logger.info("Price collection task completed successfully")

        except Exception as exc:
            session.rollback()
            logger.exception("Price collection task failed, rollback executed")
            raise exc
