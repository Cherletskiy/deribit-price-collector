from decimal import Decimal
from unittest.mock import Mock, patch

import httpx
import pytest

from collector.client import IndexChartRange, SyncDeribitClient
from collector.exceptions import (
    DeribitRequestError,
    DeribitResponseError,
    PriceBatchPermanentError,
    PriceBatchTransientError,
    UnsupportedTickerError,
)
from collector.tasks import (
    backfill_price_history,
    chunked,
    fetch_price_batch,
)


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
        mock_http_client = Mock()
        client = SyncDeribitClient(mock_http_client)

        with pytest.raises(UnsupportedTickerError, match="Unsupported ticker"):
            client.get_index_price_time("invalid_ticker")

    def test_raises_on_http_error(self):
        mock_http_client = Mock()
        mock_http_client.get.side_effect = httpx.HTTPError("Network error")
        client = SyncDeribitClient(mock_http_client)

        with pytest.raises(DeribitRequestError, match="Failed to fetch price"):
            client.get_index_price_time("btc_usd")

    def test_raises_on_malformed_response(self):
        test_cases = [
            {"usIn": 123},
            {"result": {}},
            {"result": {"index_price": "100"}, "usIn": None},
        ]

        for response_data in test_cases:
            mock_http_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_http_client.get.return_value = mock_response

            client = SyncDeribitClient(mock_http_client)

            with pytest.raises(DeribitResponseError):
                client.get_index_price_time("btc_usd")

    def test_get_index_chart_data_parses_response(self):
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                [1_609_459_200_000, "50000.00"],
                [1_609_545_600_000, "51000.00"],
            ]
        }
        mock_http_client.get.return_value = mock_response

        client = SyncDeribitClient(mock_http_client)

        points = client.get_index_chart_data("btc_usd", IndexChartRange.ONE_DAY)

        assert points == [
            (Decimal("50000.00"), 1_609_459_200),
            (Decimal("51000.00"), 1_609_545_600),
        ]

    def test_get_index_chart_data_raises_on_malformed_response(self):
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [["bad"]]}
        mock_http_client.get.return_value = mock_response

        client = SyncDeribitClient(mock_http_client)

        with pytest.raises(DeribitResponseError):
            client.get_index_chart_data("btc_usd", IndexChartRange.ONE_DAY)


class TestFetchPriceBatch:
    def test_fetch_price_batch_all_success(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = [
                (Decimal("50000"), 1234567890),
                (Decimal("3500"), 1234567890),
            ]
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                fetch_price_batch(["btc_usd", "eth_usd"])

                assert mock_client.get_index_price_time.call_count == 2
                assert mock_repo.save_price.call_count == 2
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_partial_success(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = [
                (Decimal("50000"), 1234567890),
                DeribitRequestError("API error"),
            ]
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                fetch_price_batch(["btc_usd", "eth_usd"])

                assert mock_client.get_index_price_time.call_count == 2
                mock_repo.save_price.assert_called_once_with(
                    ticker="btc_usd", price=Decimal("50000"), timestamp=1234567890
                )
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_all_transient_failures(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = DeribitRequestError(
                "API down"
            )
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                with pytest.raises(
                    PriceBatchTransientError,
                    match="Transient batch failure",
                ):
                    fetch_price_batch(["btc_usd", "eth_usd"])

                assert mock_client.get_index_price_time.call_count == 2
                mock_repo.save_price.assert_not_called()
                mock_session.rollback.assert_called_once()
                mock_session.commit.assert_not_called()
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_all_permanent_failures(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.side_effect = UnsupportedTickerError(
                "Unsupported ticker"
            )
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                with pytest.raises(
                    PriceBatchPermanentError,
                    match="Permanent batch failure",
                ):
                    fetch_price_batch(["btc_usd", "eth_usd"])

                assert mock_client.get_index_price_time.call_count == 2
                mock_repo.save_price.assert_not_called()
                mock_session.rollback.assert_called_once()
                mock_session.commit.assert_not_called()
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_updates_existing_price(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.return_value = (
                Decimal("51000"),
                1234567890,
            )
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            existing_price = Mock()
            mock_repo.save_price.return_value = existing_price

            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                fetch_price_batch(["btc_usd"])

                mock_repo.save_price.assert_called_once_with(
                    ticker="btc_usd",
                    price=Decimal("51000"),
                    timestamp=1234567890,
                )
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                mock_session.close.assert_called_once()

    def test_fetch_price_batch_commit_failure_raises_transient_error(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_price_time.return_value = (
                Decimal("51000"),
                1234567890,
            )
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_session.commit.side_effect = RuntimeError("db unavailable")
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                with pytest.raises(PriceBatchTransientError, match="Failed to commit"):
                    fetch_price_batch(["btc_usd"])

                assert mock_client.get_index_price_time.call_count == 1
                mock_repo.save_price.assert_called_once()
                mock_session.rollback.assert_called_once()
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_backfill_price_history_success(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_chart_data.return_value = [
                (Decimal("50000.00"), 1_609_459_200),
                (Decimal("51000.00"), 1_609_545_600),
            ]
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                backfill_price_history(["btc_usd"], "1d")

                assert mock_repo.save_price.call_count == 2
                mock_session.commit.assert_called_once()
                mock_session.rollback.assert_not_called()
                mock_session.close.assert_called_once()

    def test_backfill_price_history_invalid_range(self):
        mock_session = Mock()
        with patch("collector.tasks.SyncSessionLocal", return_value=mock_session):
            with pytest.raises(
                PriceBatchPermanentError,
                match="Unsupported backfill range",
            ):
                backfill_price_history(["btc_usd"], "10d")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    def test_backfill_price_history_transient_failure(self):
        with patch("collector.tasks.build_sync_market_data_provider") as MockProvider:
            mock_client = Mock()
            mock_client.get_index_chart_data.side_effect = DeribitRequestError(
                "network"
            )
            MockProvider.return_value = mock_client

            mock_session = Mock()
            mock_repo = Mock()
            with (
                patch("collector.tasks.SyncSessionLocal", return_value=mock_session),
                patch("collector.tasks.SyncPriceRepository", return_value=mock_repo),
                patch("collector.tasks.httpx.Client") as MockHttpClient,
            ):
                mock_http_client = Mock()
                MockHttpClient.return_value.__enter__.return_value = mock_http_client

                with pytest.raises(
                    PriceBatchTransientError,
                    match="Transient backfill failure",
                ):
                    backfill_price_history(["btc_usd"], "1d")

                mock_repo.save_price.assert_not_called()
                mock_session.close.assert_called_once()


def test_chunked_splits_correctly():
    """chunked правильно делит список на батчи"""
    result = list(chunked([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]
