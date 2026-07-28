class PriceCollectionError(Exception):
    pass


class PriceCollectionPermanentError(PriceCollectionError):
    pass


class PriceCollectionTransientError(PriceCollectionError):
    pass


class UnsupportedTickerError(PriceCollectionPermanentError):
    pass


class DeribitResponseError(PriceCollectionPermanentError):
    pass


class DeribitRequestError(PriceCollectionTransientError):
    pass


class PriceBatchPermanentError(PriceCollectionPermanentError):
    pass


class PriceBatchTransientError(PriceCollectionTransientError):
    pass
