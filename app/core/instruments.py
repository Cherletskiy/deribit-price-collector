from collector.providers import list_supported_instruments


def supported_ticker_set() -> frozenset[str]:
    return frozenset(instrument.ticker for instrument in list_supported_instruments())
