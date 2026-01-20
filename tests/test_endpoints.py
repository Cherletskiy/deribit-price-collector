from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import SortOrder
from app.schemas import PriceResponse


class TestEndpoints:
    """Тесты эндпоинтов"""

    def test_get_all_prices_success(self, client_direct_mock, mock_price_repository):
        """Успешное получение всех цен (без параметров пагинации)"""
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd"}
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 10
        assert data[0]["ticker"] == "btc_usd"

        assert data[0]["price"] == "50000.00"
        assert data[0]["timestamp"] == 1609459200

        # Проверяем, что вызывался правильный метод репозитория
        mock_price_repository.get_all_by_ticker.assert_called_once_with(
            ticker="btc_usd",
            limit=50,  # значение по умолчанию
            offset=0,  # значение по умолчанию
            sorting=SortOrder.ASC,  # значение по умолчанию
        )

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
        # Временно отключаем side_effect для этого метода
        original_side_effect = mock_price_repository.get_all_by_ticker.side_effect
        mock_price_repository.get_all_by_ticker.side_effect = None
        mock_price_repository.get_all_by_ticker.return_value = []

        try:
            response = client_direct_mock.get(
                "/api/v1/prices", params={"ticker": "eth_usd"}  # или "non_existent"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "No data found for this ticker"
        finally:
            # Восстанавливаем side_effect
            mock_price_repository.get_all_by_ticker.side_effect = original_side_effect

    def test_get_latest_price_success(self, client_direct_mock, mock_price_repository):
        """Успешное получение последней цены"""
        response = client_direct_mock.get(
            "/api/v1/prices/latest", params={"ticker": "btc_usd"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ticker"] == "btc_usd"
        # Последняя цена - 59000.00 (2021-01-10)
        # Таймстемп для 2021-01-10: 1610236800
        assert data["price"] == "59000.00"
        assert data["timestamp"] == 1610236800  # Исправлено!

        mock_price_repository.get_latest_by_ticker.assert_called_once_with("btc_usd")

        mock_price_repository.get_latest_by_ticker.assert_called_once_with("btc_usd")

    def test_get_latest_price_no_data(self, client_direct_mock, mock_price_repository):
        """Запрос последней цены, когда нет данных"""
        # Временно подменяем side_effect для возврата None
        original_side_effect = mock_price_repository.get_latest_by_ticker.side_effect
        mock_price_repository.get_latest_by_ticker.side_effect = None
        mock_price_repository.get_latest_by_ticker.return_value = None

        try:
            response = client_direct_mock.get(
                "/api/v1/prices/latest", params={"ticker": "eth_usd"}
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "No data found for this ticker"
        finally:
            # Восстанавливаем side_effect
            mock_price_repository.get_latest_by_ticker.side_effect = (
                original_side_effect
            )
            mock_price_repository.get_latest_by_ticker.return_value = None

    def test_get_prices_by_date_success(
        self, client_direct_mock, mock_price_repository
    ):
        """Успешное получение цен по диапазону дат"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={
                "ticker": "btc_usd",
                "timestamp_from": 1609459200,  # 2021-01-01
                "timestamp_to": 1609545600,  # 2021-01-02
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # В диапазоне от 2021-01-01 до 2021-01-02 будет 2 записи
        assert len(data) == 2
        assert data[0]["ticker"] == "btc_usd"
        # При сортировке ASC по умолчанию
        assert data[0]["timestamp"] == 1609459200  # 2021-01-01

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd",
            timestamp_from=1609459200,
            timestamp_to=1609545600,
            limit=50,  # значение по умолчанию
            offset=0,  # значение по умолчанию
            sorting=SortOrder.ASC,  # значение по умолчанию
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
            ticker="btc_usd",
            timestamp_from=1609459200,
            timestamp_to=None,
            limit=50,
            offset=0,
            sorting=SortOrder.ASC,
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
            ticker="btc_usd",
            timestamp_from=None,
            timestamp_to=1609545600,
            limit=50,
            offset=0,
            sorting=SortOrder.ASC,
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
            ticker="btc_usd",
            timestamp_from=None,
            timestamp_to=None,
            limit=50,
            offset=0,
            sorting=SortOrder.ASC,
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
        # Временно подменяем side_effect для возврата пустого списка
        original_side_effect = (
            mock_price_repository.get_by_ticker_and_date_range.side_effect
        )
        mock_price_repository.get_by_ticker_and_date_range.side_effect = None
        mock_price_repository.get_by_ticker_and_date_range.return_value = []

        try:
            response = client_direct_mock.get(
                "/api/v1/prices/by-date",
                params={"ticker": "eth_usd", "timestamp_from": 1609459200},
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "No data found for this query"
        finally:
            # Восстанавливаем side_effect
            mock_price_repository.get_by_ticker_and_date_range.side_effect = (
                original_side_effect
            )
            mock_price_repository.get_by_ticker_and_date_range.return_value = None

    # Новые тесты для пагинации и сортировки

    def test_get_all_prices_with_pagination(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест пагинации при получении всех цен"""
        response = client_direct_mock.get(
            "/api/v1/prices",
            params={
                "ticker": "btc_usd",
                "limit": 3,
                "offset": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Проверяем пагинацию
        assert len(data) == 3  # limit=3
        # Первая запись должна быть с offset=2 (при сортировке ASC)
        assert data[0]["timestamp"] == 1609632000  # 2021-01-03

        # Проверяем вызов репозитория
        mock_price_repository.get_all_by_ticker.assert_called_once_with(
            ticker="btc_usd",
            limit=3,
            offset=2,
            sorting=SortOrder.ASC,  # значение по умолчанию
        )

    def test_get_all_prices_with_sorting_desc(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест сортировки по убыванию"""
        response = client_direct_mock.get(
            "/api/v1/prices",
            params={"ticker": "btc_usd", "limit": 3, "sorting": "desc"},
        )

        assert response.status_code == 200
        data = response.json()

        # При сортировке DESC первая запись должна быть самой новой
        assert len(data) == 3
        assert (
            data[0]["timestamp"] == 1610236800
        )  # Исправлено! Последняя дата (2021-01-10)
        assert data[0]["price"] == "59000.00"  # Самая высокая цена

        mock_price_repository.get_all_by_ticker.assert_called_once_with(
            ticker="btc_usd", limit=3, offset=0, sorting=SortOrder.DESC
        )

    def test_get_all_prices_with_sorting_asc(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест сортировки по возрастанию"""
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "limit": 3, "sorting": "asc"}
        )

        assert response.status_code == 200
        data = response.json()

        # При сортировке ASC первая запись должна быть самой старой
        assert len(data) == 3
        assert data[0]["timestamp"] == 1609459200  # Первая дата (2021-01-01)
        assert data[0]["price"] == "50000.00"  # Самая низкая цена

        mock_price_repository.get_all_by_ticker.assert_called_once_with(
            ticker="btc_usd", limit=3, offset=0, sorting=SortOrder.ASC
        )

    def test_get_prices_by_date_with_pagination(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест пагинации с фильтрацией по дате"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={
                "ticker": "btc_usd",
                "timestamp_from": 1609459200,  # 2021-01-01
                "timestamp_to": 1609718400,  # 2021-01-04
                "limit": 2,
                "offset": 1,
                "sorting": "asc",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Должны получить 2 записи начиная со второй
        assert len(data) == 2
        # Первая запись после offset=1
        assert data[0]["timestamp"] == 1609545600  # 2021-01-02

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd",
            timestamp_from=1609459200,
            timestamp_to=1609718400,
            limit=2,
            offset=1,
            sorting=SortOrder.ASC,
        )

    def test_get_prices_by_date_with_sorting_desc(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест сортировки по убыванию с фильтрацией по дате"""
        response = client_direct_mock.get(
            "/api/v1/prices/by-date",
            params={
                "ticker": "btc_usd",
                "timestamp_from": 1609459200,
                "timestamp_to": 1609718400,
                "limit": 10,
                "sorting": "desc",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # При DESC первая запись должна быть самой новой в диапазоне
        assert len(data) == 4  # Всего 4 записи в диапазоне
        assert data[0]["timestamp"] == 1609718400  # Последняя дата в диапазоне
        assert data[-1]["timestamp"] == 1609459200  # Первая дата в диапазоне

        mock_price_repository.get_by_ticker_and_date_range.assert_called_once_with(
            ticker="btc_usd",
            timestamp_from=1609459200,
            timestamp_to=1609718400,
            limit=10,
            offset=0,
            sorting=SortOrder.DESC,
        )

    def test_pagination_validation(self, client_direct_mock):
        """Тест валидации параметров пагинации"""
        # limit меньше минимального
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "limit": 0}
        )
        assert response.status_code == 422
        assert "limit" in response.json()["detail"][0]["loc"]

        # limit больше максимального
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "limit": 1001}
        )
        assert response.status_code == 422

        # offset отрицательный
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "offset": -1}
        )
        assert response.status_code == 422

    def test_sorting_validation(self, client_direct_mock):
        """Тест валидации параметра сортировки"""
        # Неверное значение sorting
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "sorting": "invalid"}
        )
        assert response.status_code == 422
        assert "sorting" in response.json()["detail"][0]["loc"]

        # Корректные значения
        for sorting_value in ["asc", "desc"]:
            response = client_direct_mock.get(
                "/api/v1/prices", params={"ticker": "btc_usd", "sorting": sorting_value}
            )
            assert response.status_code == 200

    def test_edge_cases_pagination(self, client_direct_mock, mock_price_repository):
        """Тест граничных случаев пагинации"""
        # offset больше чем данных
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "offset": 100}
        )
        assert response.status_code == 404  # Нет данных

        # limit больше чем данных
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "limit": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10  # Всего 10 записей для btc_usd

    def test_multiple_tickers_pagination(
        self, client_direct_mock, mock_price_repository
    ):
        """Тест пагинации для разных тикеров"""
        # BTC
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "btc_usd", "limit": 5}
        )
        assert response.status_code == 200
        btc_data = response.json()
        assert len(btc_data) == 5
        assert all(item["ticker"] == "btc_usd" for item in btc_data)

        # ETH
        response = client_direct_mock.get(
            "/api/v1/prices", params={"ticker": "eth_usd", "limit": 3}
        )
        assert response.status_code == 200
        eth_data = response.json()
        assert len(eth_data) == 3
        assert all(item["ticker"] == "eth_usd" for item in eth_data)


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

    def test_pagination_default_values(self, simple_client):
        """Тест значений по умолчанию для пагинации"""
        # Мокаем репозиторий для этого теста
        from unittest.mock import AsyncMock, patch

        mock_repo = AsyncMock()
        mock_repo.get_all_by_ticker.return_value = []

        with patch("app.api.endpoints.AsyncPriceRepository", return_value=mock_repo):
            response = simple_client.get("/api/v1/prices", params={"ticker": "btc_usd"})

            # Проверяем, что вызвался с значениями по умолчанию
            mock_repo.get_all_by_ticker.assert_called_once_with(
                ticker="btc_usd",
                limit=50,  # значение по умолчанию
                offset=0,  # значение по умолчанию
                sorting=SortOrder.ASC,  # значение по умолчанию
            )


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
