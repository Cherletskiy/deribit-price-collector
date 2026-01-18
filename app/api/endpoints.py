from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.schemas import PriceResponse
from app.services import PriceService
from app.repositories import AsyncPriceRepository

router = APIRouter(prefix="/api/v1", tags=["prices"])


@router.get("/prices")
async def get_all_prices(
    ticker: str = Query(..., description="Тикер валюты", enum=["btc_usd", "eth_usd"]),
    db: AsyncSession = Depends(get_async_session),
) -> list[PriceResponse]:
    """
    Получение всех сохранённых данных по указанной валюте.
    """
    repo = AsyncPriceRepository(db)
    service = PriceService(repo)
    prices = await service.get_all_prices(ticker)
    if not prices:
        raise HTTPException(status_code=404, detail="No data found for this ticker")
    return [PriceResponse.from_orm(price) for price in prices]


@router.get("/prices/latest")
async def get_latest_price(
    ticker: str = Query(..., description="Тикер валюты", enum=["btc_usd", "eth_usd"]),
    db: AsyncSession = Depends(get_async_session),
) -> PriceResponse:
    """
    Получение последней цены валюты.
    """
    repo = AsyncPriceRepository(db)
    service = PriceService(repo)
    price = await service.get_latest_price(ticker)
    if price is None:
        raise HTTPException(status_code=404, detail="No data found for this ticker")
    return PriceResponse.from_orm(price)


@router.get("/prices/by-date")
async def get_prices_by_date(
    ticker: str = Query(..., description="Тикер валюты", enum=["btc_usd", "eth_usd"]),
    timestamp_from: int | None = Query(None, description="Начальное время (UNIX timestamp)"),
    timestamp_to: int | None  = Query(None, description="Конечное время (UNIX timestamp)"),
    db: AsyncSession = Depends(get_async_session),
) -> list[PriceResponse]:
    """
    Получение цены валюты с фильтром по дате (UNIX timestamp).
    """
    # Валидация временного диапазона
    if timestamp_from is not None:
        if timestamp_from < 0 or timestamp_from > 2_500_000_000:
            raise HTTPException(
                status_code=400,
                detail="timestamp_from must be a valid UNIX timestamp (0 <= timestamp <= 2500000000)"
            )
    if timestamp_to is not None:
        if timestamp_to < 0 or timestamp_to > 2_500_000_000:
            raise HTTPException(
                status_code=400,
                detail="timestamp_to must be a valid UNIX timestamp (0 <= timestamp <= 2500000000)"
            )
    if timestamp_from is not None and timestamp_to is not None:
        if timestamp_from > timestamp_to:
            raise HTTPException(
                status_code=400,
                detail="timestamp_from must be less than or equal to timestamp_to"
            )

    repo = AsyncPriceRepository(db)
    service = PriceService(repo)
    prices = await service.get_prices_by_date_range(
        ticker=ticker,
        timestamp_from=timestamp_from,
        timestamp_to=timestamp_to,
    )
    if not prices:
        raise HTTPException(status_code=404, detail="No data found for this query")
    return [PriceResponse.from_orm(price) for price in prices]
