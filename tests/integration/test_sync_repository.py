from decimal import Decimal

from app.models import Price
from app.repositories import SyncPriceRepository


def test_sync_price_repository_save_price(test_db_sync_session):
    """
    SyncPriceRepository корректно сохраняет цену в БД
    """
    session = test_db_sync_session
    repo = SyncPriceRepository(session)

    price = repo.save_price(
        ticker="btc_usd",
        price=Decimal("45000.50"),
        timestamp=1700000000,
    )

    session.commit()

    # Проверяем что объект в БД
    saved = session.query(Price).filter_by(ticker="btc_usd").one()

    assert saved.id is not None
    assert saved.ticker == "btc_usd"
    assert saved.price == Decimal("45000.50")
    assert saved.timestamp == 1700000000
