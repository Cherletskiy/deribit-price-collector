from collections.abc import Iterable
from itertools import islice
from time import time

import httpx
from celery import Celery

from app.core.config import config
from app.core.db import SyncSessionLocal
from app.core.logging_config import setup_logger
from app.repositories import SyncPriceRepository
from collector.exceptions import (
    PriceBatchPermanentError,
    PriceBatchTransientError,
    PriceCollectionPermanentError,
    PriceCollectionTransientError,
)
from collector.providers import HistoryRange, build_sync_market_data_provider

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
    },
    "reconcile-recent-prices": {
        "task": "collector.tasks.reconcile_recent_prices",
        "schedule": config.RECONCILIATION_INTERVAL_SEC,
    },
}


def resolve_reconciliation_range(lookback_seconds: int) -> HistoryRange:
    if lookback_seconds <= 3600:
        return HistoryRange.ONE_HOUR
    if lookback_seconds <= 86400:
        return HistoryRange.ONE_DAY
    if lookback_seconds <= 172800:
        return HistoryRange.TWO_DAYS
    if lookback_seconds <= 31 * 86400:
        return HistoryRange.ONE_MONTH
    if lookback_seconds <= 366 * 86400:
        return HistoryRange.ONE_YEAR
    return HistoryRange.ALL


def has_missing_intervals(
    timestamps: list[int],
    expected_step_sec: int,
    stale_multiplier: int,
) -> bool:
    if len(timestamps) < 2:
        return False

    max_allowed_gap = expected_step_sec * stale_multiplier
    return any(
        current_timestamp - previous_timestamp > max_allowed_gap
        for previous_timestamp, current_timestamp in zip(
            timestamps,
            timestamps[1:],
            strict=False,
        )
    )


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
    expires=240,
    name="collector.tasks.reconcile_recent_prices",
)
def reconcile_recent_prices(
    tickers: list[str] | None = None,
    lookback_seconds: int | None = None,
) -> None:
    selected_tickers = tickers or list(config.supported_tickers)
    effective_lookback = lookback_seconds or config.RECONCILIATION_LOOKBACK_SEC
    now_timestamp = int(time())
    range_start = now_timestamp - effective_lookback
    stale_multiplier = config.RECONCILIATION_STALE_MULTIPLIER
    expected_step_sec = config.PRICE_FETCH_INTERVAL_SEC
    backfill_tickers: list[str] = []

    logger.info(
        "Starting reconciliation | tickers=%s | lookback_seconds=%d",
        selected_tickers,
        effective_lookback,
    )

    session = SyncSessionLocal()
    try:
        repo = SyncPriceRepository(session)

        for ticker in selected_tickers:
            latest_timestamp = repo.get_latest_timestamp(ticker)
            timestamps = repo.get_timestamps_in_range(
                ticker=ticker,
                timestamp_from=range_start,
                timestamp_to=now_timestamp,
            )

            if latest_timestamp is None:
                backfill_tickers.append(ticker)
                logger.warning(
                    "Reconciliation detected empty history | ticker=%s",
                    ticker,
                )
                continue

            if now_timestamp - latest_timestamp > expected_step_sec * stale_multiplier:
                backfill_tickers.append(ticker)
                logger.warning(
                    (
                        "Reconciliation detected stale latest price "
                        "| ticker=%s | latest_timestamp=%d"
                    ),
                    ticker,
                    latest_timestamp,
                )
                continue

            if has_missing_intervals(
                timestamps=timestamps,
                expected_step_sec=expected_step_sec,
                stale_multiplier=stale_multiplier,
            ):
                backfill_tickers.append(ticker)
                logger.warning(
                    "Reconciliation detected missing intervals | ticker=%s",
                    ticker,
                )

        if not backfill_tickers:
            logger.info("Reconciliation completed without gaps")
            return

        history_range = resolve_reconciliation_range(effective_lookback)
        backfill_price_history.delay(
            tickers=backfill_tickers,
            range_name=history_range.value,
        )
        logger.info(
            "Scheduled reconciliation backfill | tickers=%s | range=%s",
            backfill_tickers,
            history_range.value,
        )
    finally:
        session.close()


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
            client = build_sync_market_data_provider(http_client)

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


@celery_app.task(
    autoretry_for=(PriceBatchTransientError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    expires=300,
    name="collector.tasks.backfill_price_history",
)
def backfill_price_history(
    tickers: list[str],
    range_name: str,
) -> None:
    logger.info(
        "Starting backfill | tickers=%s | range=%s",
        tickers,
        range_name,
    )

    session = SyncSessionLocal()
    total_saved = 0
    try:
        repo = SyncPriceRepository(session)
        chart_range = HistoryRange(range_name)

        with httpx.Client(timeout=config.DERIBIT_API_TIMEOUT_SEC) as http_client:
            client = build_sync_market_data_provider(http_client)

            for ticker in tickers:
                try:
                    points = client.get_index_chart_data(ticker, chart_range)
                except PriceCollectionPermanentError as exc:
                    logger.error(
                        "Permanent backfill failure | ticker=%s | range=%s | error=%s",
                        ticker,
                        range_name,
                        exc,
                    )
                    continue
                except PriceCollectionTransientError as exc:
                    raise PriceBatchTransientError(
                        f"Transient backfill failure for {ticker}: {exc}"
                    ) from exc

                for price, timestamp in points:
                    repo.save_price(ticker=ticker, price=price, timestamp=timestamp)
                    total_saved += 1

        try:
            session.commit()
        except Exception as exc:
            session.rollback()
            raise PriceBatchTransientError(
                f"Failed to commit backfill prices: {exc}"
            ) from exc

        logger.info(
            "Backfill completed | tickers=%s | range=%s | points_saved=%d",
            tickers,
            range_name,
            total_saved,
        )
    except ValueError as exc:
        session.rollback()
        raise PriceBatchPermanentError(
            f"Unsupported backfill range {range_name}: {exc}"
        ) from exc
    finally:
        session.close()
