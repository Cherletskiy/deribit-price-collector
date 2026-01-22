from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.main import app
from app.models import Price
from app.repositories import AsyncPriceRepository, SortOrder


# Фикстуры для моков
@pytest_asyncio.fixture()
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def create_db_schema(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_session(async_engine):
    session_maker = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def test_async_price_repository(async_session):
    return AsyncPriceRepository(async_session)


@pytest_asyncio.fixture
async def sample_price_data(async_session):
    prices = [
        Price(
            ticker="btc_usd",
            price=Decimal("45000.50"),
            timestamp=1700000000,
        ),
        Price(
            ticker="btc_usd",
            price=Decimal("45500.75"),
            timestamp=1700000100,
        ),
        Price(
            ticker="eth_usd",
            price=Decimal("3200.25"),
            timestamp=1700000050,
        ),
    ]

    async_session.add_all(prices)
    await async_session.commit()

    return prices


@pytest.fixture
def sync_engine():
    """
    Синхронный движок для SQLite.
    StaticPool - чтобы БД в памяти жила всё время теста.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_sync_session(sync_engine):
    """
    Синхронная сессия для интеграционных тестов
    """
    Session = sessionmaker(bind=sync_engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_price_data():
    """Фиктивные данные о ценах (10 записей для тестирования пагинации)"""
    base_date = datetime(2021, 1, 1, 0, 0, 0)
    prices = []

    # Создаем 10 записей с разными датами и ценами
    for i in range(10):
        price_data = {
            "ticker": "btc_usd",
            "price": Decimal(f"{50000 + i * 1000}.00"),  # 50000, 51000, 52000...
            "timestamp": int((base_date + timedelta(days=i)).timestamp()),
            "created_at": base_date + timedelta(days=i),
        }
        prices.append(price_data)

    # Добавляем еще 5 записей для другого тикера
    for i in range(5):
        price_data = {
            "ticker": "eth_usd",
            "price": Decimal(f"{3000 + i * 100}.00"),  # 3000, 3100, 3200...
            "timestamp": int((base_date + timedelta(days=i)).timestamp()),
            "created_at": base_date + timedelta(days=i),
        }
        prices.append(price_data)

    return prices


@pytest.fixture
def mock_price_models(mock_price_data):
    """Фиктивные ORM модели"""
    models = []
    for data in mock_price_data:
        mock_model = MagicMock()
        mock_model.ticker = data["ticker"]
        mock_model.price = data["price"]
        mock_model.timestamp = data["timestamp"]
        mock_model.created_at = data["created_at"]
        models.append(mock_model)
    return models


@pytest.fixture
def mock_price_repository(mock_price_models):
    """Мок репозитория с поддержкой пагинации и сортировки"""
    repository = AsyncMock()

    # Фильтруем модели по тикеру
    btc_models = [m for m in mock_price_models if m.ticker == "btc_usd"]
    eth_models = [m for m in mock_price_models if m.ticker == "eth_usd"]

    # Методы с параметрами пагинации
    def get_all_by_ticker_side_effect(
        ticker, limit=50, offset=0, sorting=SortOrder.ASC
    ):
        models = btc_models if ticker == "btc_usd" else eth_models

        # Применяем сортировку
        if sorting == SortOrder.DESC:
            models = sorted(models, key=lambda x: x.timestamp, reverse=True)
        else:
            models = sorted(models, key=lambda x: x.timestamp)

        # Применяем пагинацию
        return models[offset : offset + limit]

    def get_by_ticker_and_date_range_side_effect(
        ticker,
        timestamp_from=None,
        timestamp_to=None,
        limit=50,
        offset=0,
        sorting=SortOrder.ASC,
    ):
        models = btc_models if ticker == "btc_usd" else eth_models

        # Фильтрация по дате
        if timestamp_from is not None:
            models = [m for m in models if m.timestamp >= timestamp_from]
        if timestamp_to is not None:
            models = [m for m in models if m.timestamp <= timestamp_to]

        # Сортировка
        if sorting == SortOrder.DESC:
            models = sorted(models, key=lambda x: x.timestamp, reverse=True)
        else:
            models = sorted(models, key=lambda x: x.timestamp)

        # Пагинация
        return models[offset : offset + limit]

    # Настраиваем моки с side_effect для более реалистичного поведения
    repository.get_all_by_ticker.side_effect = get_all_by_ticker_side_effect
    repository.get_latest_by_ticker.side_effect = lambda ticker: (
        sorted(
            [m for m in mock_price_models if m.ticker == ticker],
            key=lambda x: x.timestamp,
            reverse=True,
        )[0]
        if any(m.ticker == ticker for m in mock_price_models)
        else None
    )
    repository.get_by_ticker_and_date_range.side_effect = (
        get_by_ticker_and_date_range_side_effect
    )

    return repository


@pytest.fixture
def client_direct_mock(mock_price_repository):
    """Клиент с прямым моком репозитория в эндпоинтах"""
    with patch("app.api.endpoints.AsyncPriceRepository") as mock_repo_class:
        mock_repo_class.return_value = mock_price_repository

        with TestClient(app) as test_client:
            yield test_client
