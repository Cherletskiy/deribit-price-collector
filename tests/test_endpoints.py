from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import PriceResponse


class TestEndpoints:
    """Тесты эндпоинтов"""

    def test_get_all_prices_success(self, client_direct_mock, mock_price_repository):
        """Успешное получение всех цен"""
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd"}
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["ticker"] == "btc_usd"
        assert data[0]["price"] == "50000.00"
        assert data[0]["timestamp"] == 1609459200

        # Проверяем, что вызывался правильный метод репозитория
        mock_price_repository.get_all_by_ticker.assert_called_once_with("btc_usd")

    def test_get_all_prices_invalid_ticker(self, client_direct_mock):
        """Запрос с невалидным тикером"""
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "invalid_ticker"}
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "literal_error"

    def test_get_all_prices_no_data(self, client_direct_mock, mock_price_repository):
        """Запрос, когда нет данных"""
        # Настраиваем репозиторий на возврат пустого списка
        mock_price_repository.get_all_by_ticker.return_value = []

        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "eth_usd"}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "No data found for this ticker"

    def test_get_latest_price_success(self, client_direct_mock, mock_price_repository):
        """Успешное получение последней цены"""
        response = client_direct_mock.get(
            "/api/v1/prices/latest", params={"ticker": "btc_usd"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "btc_usd"
        assert data["price"] == "51000.00"
        assert data["timestamp"] == 1609545600

        mock_price_repository.get_latest_by_ticker.assert_called_once_with("btc_usd")

    def test_get_latest_price_no_data(self, client_direct_mock, mock_price_repository):
        """Запрос последней цены, когда нет данных"""
        mock_price_repository.get_latest_by_ticker.return_value = None

        response = client_direct_mock.get(
            "/api/v1/prices/latest", params={"ticker": "eth_usd"}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "No data found for this ticker"

    def test_get_prices_by_date_success(
        self, client_direct_mock, mock_price_repository
    ):
        """Успешное получение цен по диапазону дат"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={
                "ticker": "btc_usd",
                "timestamp_from": 1609459200,
                "timestamp_to": 1609545600,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["ticker"] == "btc_usd"

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd", timestamp_from=1609459200, timestamp_to=1609545600
        )

    def test_get_prices_by_date_only_from(
        self, client_direct_mock, mock_price_repository
    ):
        """Запрос цен с указанием только начальной даты"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={"ticker": "btc_usd", "timestamp_from": 1609459200},
        )

        assert response.status_code == 200

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd", timestamp_from=1609459200, timestamp_to=None
        )

    def test_get_prices_by_date_only_to(
        self, client_direct_mock, mock_price_repository
    ):
        """Запрос цен с указанием только конечной даты"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={"ticker": "btc_usd", "timestamp_to": 1609545600},
        )

        assert response.status_code == 200

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd", timestamp_from=None, timestamp_to=1609545600
        )

    def test_get_prices_by_date_no_filters(
        self, client_direct_mock, mock_price_repository
    ):
        """Запрос цен без указания дат"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date", params={"ticker": "btc_usd"}
        )

        assert response.status_code == 200

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd", timestamp_from=None, timestamp_to=None
        )

    def test_get_prices_by_date_invalid_timestamp(self, client_direct_mock):
        """Запрос с невалидным timestamp"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date", params={"ticker": "btc_usd", "timestamp_from": -1}
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "Timestamp must be a valid UNIX timestamp" in error_detail["msg"]

    def test_get_prices_by_date_invalid_range(self, client_direct_mock):
        """Запрос с некорректным диапазоном дат"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={
                "ticker": "btc_usd",
                "timestamp_from": 1609545600,
                "timestamp_to": 1609459200,
            },
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert (
            "timestamp_from must be less than or equal to timestamp_to"
            in error_detail["msg"]
        )

    def test_get_prices_by_date_no_data(
        self, client_direct_mock, mock_price_repository
    ):
        """Запрос по датам, когда нет данных"""
        mock_price_repository.get_by_ticker_and_date_range.return_value = []

        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={"ticker": "eth_usd", "timestamp_from": 1609459200},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "No data found for this query"


class TestQueryParameters:
    """Тесты валидации query-параметров"""

    @pytest.fixture
    def simple_client(self):
        """Простой клиент без моков для тестов валидации"""
        return TestClient(app)

    def test_ticker_case_sensitivity(self, simple_client):
        """Проверка чувствительности к регистру тикера"""
        response = simple_client.get("/api/v1/prices", params={"ticker": "BTC_USD"})
        assert response.status_code == 422

    def test_missing_required_parameter(self, simple_client):
        """Проверка обязательных параметров"""
        response = simple_client.get("/api/v1/prices")
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert error_detail["type"] == "missing"

    def test_timestamp_max_value(self, simple_client):
        """Проверка максимального значения timestamp"""
        response = simple_client.get(
            "/api/v1/prices/by-date",
            params={"ticker": "btc_usd", "timestamp_from": 2_500_000_001},
        )
        assert response.status_code == 422
        assert "2500000000" in response.json()["detail"][0]["msg"]


def test_response_schema_validation():
    """Проверка схемы ответа"""
    price_response_data = {
        "ticker": "btc_usd",
        "price": "50000.00",
        "timestamp": 1609459200,
        "created_at": "2021-01-01T00:00:00",
    }

    price_response = PriceResponse(**price_response_data)
    assert price_response.ticker == "btc_usd"
    assert price_response.price == Decimal("50000.00")

    # Проверяем валидацию лишних полей
    invalid_data = price_response_data.copy()
    invalid_data["extra_field"] = "should_fail"

    with pytest.raises(ValueError) as exc_info:
        PriceResponse(**invalid_data)
    assert "extra_field" in str(exc_info.value)
