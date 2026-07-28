from decimal import Decimal
from unittest.mock import Mock, patch

import httpx
import pytest

from collector.tasks import SyncDeribitClient, chunked, fetch_price_batch


class TestSyncDeribitClient:
    def test_client_parses_api_response_correctly(self):
        """Клиент корректно парсит ответ API"""
        # Создаем мок httpx.Client
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usIn": 1_769_082_445_362_975,
            "result": {"index_price": "42500.50"},
        }
        mock_http_client.get.return_value = mock_response

        # Создаем клиент с моком
        client = SyncDeribitClient(mock_http_client)

        # Вызываем
        price, timestamp = client.get_index_price_time("btc_usd")

        # Проверяем
        assert price == Decimal("42500.50")
        assert timestamp == 1_769_082_445

        # Проверяем вызов httpx
        mock_http_client.get.assert_called_once_with(
            f"{client.BASE_URL}/public/get_index_price",
            params={"index_name": "btc_usd"},
        )

    def test_raises_on_invalid_ticker(self):
        """Клиент выбрасывает ValueError для неподдерживаемого тикера"""
        mock_http_client = Mock()
        client = SyncDeribitClient(mock_http_client)

        with pytest.raises(ValueError, match="Unsupported ticker"):
            client.get_index_price_time("invalid_ticker")

    def test_raises_on_http_error(self):
        """Клиент пробрасывает HTTP ошибки"""
        mock_http_client = Mock()
        mock_http_client.get.side_effect = httpx.HTTPError("Network error")
        client = SyncDeribitClient(mock_http_client)

        with pytest.raises(httpx.HTTPError):
            client.get_index_price_time("btc_usd")

    def test_raises_on_malformed_response(self):
        """Клиент выбрасывает ValueError при некорректном ответе API"""
        test_cases = [
            {"usIn": 123},  # нет result
            {"result": {}},  # нет index_price
            {"result": {"index_price": "100"}, "usIn": None},  # нет usIn
        ]

        for response_data in test_cases:
            mock_http_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_http_client.get.return_value = mock_response

            client = SyncDeribitClient(mock_http_client)

            with pytest.raises(ValueError):
                client.get_index_price_time("btc_usd")


class TestFetchPriceBatch:
    def test_fetch_price_batch_all_success(self):
        """Все тикеры успешно обработаны"""
        with patch("collector.tasks.SyncDeribitClient") as MockClient:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = [
                (Decimal("50000"), 1234567890),
                (Decimal("3500"), 1234567890),
            ]
            MockClient.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                # Мокаем httpx.Client контекстный менеджер
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                fetch_price_batch(["btc_usd", "eth_usd"])

                # Проверяем:
                assert mock_client.get_index_price_time.call_count == 2
                assert mock_repo.save_price.call_count == 2
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                # Проверяем что сессия закрылась
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_partial_success(self):
        """При ошибке одного тикера остальные сохраняются"""
        with patch("collector.tasks.SyncDeribitClient") as MockClient:
            mock_client = Mock()
            # Первый успешен, второй падает
            mock_client.get_index_price_time.side_effect = [
                (Decimal("50000"), 1234567890),  # btc_usd - OK
                Exception("API error"),  # eth_usd - FAIL
            ]
            MockClient.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                # Мокаем httpx.Client
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                # Вызываем
                fetch_price_batch(["btc_usd", "eth_usd"])

                # Проверяем:
                # 1. Оба тикера были обработаны
                assert mock_client.get_index_price_time.call_count == 2

                # 2. Успешный тикер сохранен
                mock_repo.save_price.assert_called_once_with(
                    ticker="btc_usd", price=Decimal("50000"), timestamp=1234567890
                )

                # 3. Commit был (т.к. есть успехи)
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                # 4. Сессия закрылась
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_all_failed(self):
        """Если все тикеры упали - rollback и исключение"""
        with patch("collector.tasks.SyncDeribitClient") as MockClient:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = Exception("API down")
            MockClient.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                # Мокаем httpx.Client
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                # Ожидаем исключение
                with pytest.raises(Exception, match="All tickers failed"):
                    fetch_price_batch(["btc_usd", "eth_usd"])

                # Проверяем:
                # 1. Оба тикера пытались обработаться
                assert mock_client.get_index_price_time.call_count == 2

                # 2. Ничего не сохранилось
                mock_repo.save_price.assert_not_called()

                # 3. Был rollback (все упали) и commit не был вызван
                mock_session.rollback.assert_called_once()
                mock_session.commit.assert_not_called()
                # 4. Сессия закрылась в finally
                mock_session.close.assert_called_once()


def test_chunked_splits_correctly():
    """chunked правильно делит список на батчи"""
    result = list(chunked([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]
