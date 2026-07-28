from decimal import Decimal

import pytest


@pytest.mark.anyio
class TestAsyncPriceRepository:
    """Интеграционные тесты для AsyncPriceRepository"""

    async def test_get_all_by_ticker(
        self, test_async_price_repository, sample_price_data
    ):
        """Получение всех цен по тикеру"""
        repo = test_async_price_repository

        # Получаем BTC цены
        btc_prices = await repo.get_all_by_ticker("btc_usd")
        assert len(btc_prices) == 2
        assert all(p.ticker == "btc_usd" for p in btc_prices)
        assert btc_prices[0].timestamp == 1700000000  # Проверяем сортировку asc

        # Получаем ETH цены
        eth_prices = await repo.get_all_by_ticker("eth_usd")
        assert len(eth_prices) == 1
        assert eth_prices[0].ticker == "eth_usd"

        # Несуществующий тикер
        empty_prices = await repo.get_all_by_ticker("unknown")
        assert len(empty_prices) == 0

    async def test_get_latest_by_ticker(
        self, test_async_price_repository, sample_price_data
    ):
        """Получение последней цены"""
        repo = test_async_price_repository

        # Последняя BTC цена (самый большой timestamp)
        latest_btc = await repo.get_latest_by_ticker("btc_usd")
        assert latest_btc is not None
        assert latest_btc.ticker == "btc_usd"
        assert latest_btc.timestamp == 1700000100
        assert latest_btc.price == Decimal("45500.75")

        # Последняя ETH цена
        latest_eth = await repo.get_latest_by_ticker("eth_usd")
        assert latest_eth.ticker == "eth_usd"

        # Несуществующий тикер
        latest_unknown = await repo.get_latest_by_ticker("unknown")
        assert latest_unknown is None

    async def test_get_by_ticker_and_date_range(
        self, test_async_price_repository, sample_price_data
    ):
        """Фильтрация по диапазону времени"""
        repo = test_async_price_repository

        # Диапазон включает оба BTC price
        prices = await repo.get_by_ticker_and_date_range(
            ticker="btc_usd",
            timestamp_from=1700000000,
            timestamp_to=1700000100,
        )
        assert len(prices) == 2

        # Только более новая цена
        prices = await repo.get_by_ticker_and_date_range(
            ticker="btc_usd",
            timestamp_from=1700000050,
            timestamp_to=1700000100,
        )
        assert len(prices) == 1
        assert prices[0].timestamp == 1700000100

        # Только timestamp_from
        prices = await repo.get_by_ticker_and_date_range(
            ticker="btc_usd",
            timestamp_from=1700000050,
            timestamp_to=None,
        )
        assert len(prices) == 1

        # Только timestamp_to
        prices = await repo.get_by_ticker_and_date_range(
            ticker="btc_usd",
            timestamp_from=None,
            timestamp_to=1700000050,
        )
        assert len(prices) == 1
        assert prices[0].timestamp == 1700000000

        # Без фильтров
        prices = await repo.get_by_ticker_and_date_range(
            ticker="btc_usd",
            timestamp_from=None,
            timestamp_to=None,
        )
        assert len(prices) == 2
