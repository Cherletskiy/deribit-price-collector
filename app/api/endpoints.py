from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.db import get_async_session, ping_db
from app.core.metrics import runtime_metrics
from app.repositories import AsyncPriceRepository
from app.schemas import (
    PriceByDateQuery,
    PriceResponse,
    TickerQuery,
    TickerWithPaginationQuery,
)
from app.services import PriceService

router = APIRouter(prefix="/api/v1", tags=["prices"])


@router.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness_check() -> dict[str, str]:
    await ping_db()
    return {"status": "ready"}


@router.get("/metrics")
async def get_runtime_metrics() -> dict[str, object]:
    return runtime_metrics.snapshot()


@router.get("/instruments")
async def get_supported_instruments() -> list[str]:
    return list(config.supported_tickers)


@router.get("/prices")
async def get_all_prices(
    query: TickerWithPaginationQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
) -> list[PriceResponse]:
    repo = AsyncPriceRepository(db)
    service = PriceService(repo)

    prices = await service.get_all_prices(
        ticker=query.ticker,
        limit=query.limit,
        offset=query.offset,
        sorting=query.sorting,
    )

    if not prices:
        raise HTTPException(status_code=404, detail="No data found for this ticker")

    return [PriceResponse.model_validate(price) for price in prices]


@router.get("/prices/latest")
async def get_latest_price(
    query: TickerQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
) -> PriceResponse:
    repo = AsyncPriceRepository(db)
    service = PriceService(repo)
    price = await service.get_latest_price(query.ticker)
    if price is None:
        raise HTTPException(status_code=404, detail="No data found for this ticker")
    return PriceResponse.model_validate(price)


@router.get("/prices/by-date")
async def get_prices_by_date(
    query: PriceByDateQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
) -> list[PriceResponse]:
    repo = AsyncPriceRepository(db)
    service = PriceService(repo)

    prices = await service.get_prices_by_date_range(
        ticker=query.ticker,
        timestamp_from=query.timestamp_from,
        timestamp_to=query.timestamp_to,
        limit=query.limit,
        offset=query.offset,
        sorting=query.sorting,
    )

    if not prices:
        raise HTTPException(status_code=404, detail="No data found for this query")

    return [PriceResponse.model_validate(price) for price in prices]
