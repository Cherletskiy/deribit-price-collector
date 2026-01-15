import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from collector.tasks import _fetch_prices_async

@pytest.mark.asyncio
async def test_fetch_prices_async():
    tickers = ["btc_usd", "eth_usd"]
    timestamp = 11111111111111

    # Мок клиента с async context manager
    mock_client_instance = AsyncMock()
    mock_client_instance.get_index_price.side_effect = [
        (Decimal("30000.12345678"), timestamp),  # BTC
        (Decimal("2000.87654321"), timestamp),   # ETH
    ]

    # Мок __aenter__/__aexit__ для async with
    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client_instance
    mock_client.__aexit__.return_value = None

    # Мок репо
    mock_repo = AsyncMock()

    with patch("collector.tasks.DeribitClient", return_value=mock_client):
        with patch("collector.tasks.PriceRepository", return_value=mock_repo):
            await _fetch_prices_async(tickers, mock_repo)

    # get_index_price был вызван для обоих тикеров
    assert mock_client_instance.get_index_price.call_count == 2
    mock_client_instance.get_index_price.assert_any_call("btc_usd")
    mock_client_instance.get_index_price.assert_any_call("eth_usd")

    # save_price был вызван дважды
    assert mock_repo.save_price.call_count == 2
