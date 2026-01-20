from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# Фикстуры для моков
@pytest.fixture
def mock_price_data():
    """Фиктивные данные о ценах"""
    return [
        {
            "ticker": "btc_usd",
            "price": Decimal("50000.00"),
            "timestamp": 1609459200,  # 2021-01-01
            "created_at": datetime(2021, 1, 1, 0, 0, 0),
        },
        {
            "ticker": "btc_usd",
            "price": Decimal("51000.00"),
            "timestamp": 1609545600,  # 2021-01-02
            "created_at": datetime(2021, 1, 2, 0, 0, 0),
        },
    ]


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
    """Мок репозитория"""
    repository = AsyncMock()

    repository.get_all_by_ticker = AsyncMock(return_value=mock_price_models)
    repository.get_latest_by_ticker = AsyncMock(return_value=mock_price_models[-1])
    repository.get_by_ticker_and_date_range = AsyncMock(
        return_value=mock_price_models[0:1]
    )

    return repository


@pytest.fixture
def client(mock_price_repository):
    """Тестовый клиент с подменой зависимостей"""
    # Патчим репозиторий в сервисе
    with patch("app.services.PriceService") as MockService:
        mock_service_instance = AsyncMock()

        # Создаем моки для методов сервиса
        mock_service_instance.get_all_prices = AsyncMock(
            return_value=mock_price_repository.get_all_by_ticker.return_value
        )
        mock_service_instance.get_latest_price = AsyncMock(
            return_value=mock_price_repository.get_latest_by_ticker.return_value
        )
        mock_service_instance.get_prices_by_date_range = AsyncMock(
            return_value=mock_price_repository.get_by_ticker_and_date_range.return_value
        )

        MockService.return_value = mock_service_instance

        # Создаем TestClient
        with TestClient(app) as test_client:
            yield test_client


# Альтернативная фикстура, если нужно патчить репозиторий напрямую
@pytest.fixture
def client_direct_mock(mock_price_repository):
    """Клиент с прямым моком репозитория в эндпоинтах"""
    with patch("app.api.endpoints.AsyncPriceRepository") as mock_repo_class:
        mock_repo_class.return_value = mock_price_repository

        with TestClient(app) as test_client:
            yield test_client
