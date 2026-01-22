import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from app.core.config import Config
from collector.tasks import SyncDeribitClient, fetch_price_batch, chunked


class TestSyncDeribitClient:
    def test_client_parses_api_response_correctly(self):
        """Клиент корректно парсит ответ Deribit API"""
        client = SyncDeribitClient()

        with patch('requests.get') as mock_get:
            # Мокаем успешный ответ API
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "usIn": 1769082445362975,  # микросекунды
                "result": {
                    "index_price": "42500.50"
                }
            }
            mock_get.return_value = mock_response

            # Вызываем
            price, timestamp = client.get_index_price_time("btc_usd")

            # Проверяем
            assert price == Decimal("42500.50")
            assert timestamp == 1769082445  # секунды (usIn // 1_000_000)
            mock_get.assert_called_once_with(
                f"{Config.DERIBIT_API_BASE_URL.rstrip('/')}/public/get_index_price",
                params={"index_name": "btc_usd"},
                timeout=10
            )

    def test_raises_on_invalid_ticker(self):
        client = SyncDeribitClient()
        with pytest.raises(ValueError, match="Unsupported ticker"):
            client.get_index_price_time("invalid_ticker")


class TestFetchPriceBatch:
    def test_fetch_price_batch_saves_all_prices(self):
        """Успешно сохраняет все цены из батча"""
        with patch('collector.tasks.SyncDeribitClient') as MockClient:
            mock_client = Mock()
            # Возвращаем разные цены для разных тикеров
            mock_client.get_index_price_time.side_effect = [
                (Decimal("50000"), 1234567890),  # btc_usd
                (Decimal("3500"), 1234567890),  # eth_usd
            ]
            MockClient.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with patch('collector.tasks.SyncSessionLocal', return_value=mock_session), \
                    patch('collector.tasks.SyncPriceRepository', return_value=mock_repo):
                # Вызываем
                fetch_price_batch(['btc_usd', 'eth_usd'])

                # Проверяем
                assert mock_client.get_index_price_time.call_count == 2
                assert mock_repo.save_price.call_count == 2
                mock_session.commit.assert_called_once()


    def test_fetch_price_batch_rollback_on_api_failure(self):
        """При ошибке API происходит rollback, а не commit"""
        with patch('collector.tasks.SyncDeribitClient') as MockClient:
            # Настраиваем моки
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = Exception("API недоступен")
            MockClient.return_value = mock_client

            mock_session = Mock()
            with patch('collector.tasks.SyncSessionLocal', return_value=mock_session):
                # Вызываем задачу
                with pytest.raises(Exception):
                    fetch_price_batch(['btc_usd', 'eth_usd'])

                # При ошибке был rollback, а НЕ commit
                mock_session.rollback.assert_called_once()
                mock_session.commit.assert_not_called()
                mock_session.close.assert_called_once()



def test_chunked_splits_correctly():
    """chunked правильно делит список на батчи"""
    result = list(chunked([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]