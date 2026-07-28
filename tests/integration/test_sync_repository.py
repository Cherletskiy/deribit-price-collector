from decimal import Decimal

from app.models import Price
from app.repositories import SyncPriceRepository


def test_sync_price_repository_save_price(test_db_sync_session):
    session = test_db_sync_session
    repo = SyncPriceRepository(session)

    repo.save_price(
        ticker="btc_usd",
        price=Decimal("45000.50"),
        timestamp=1700000000,
    )

    session.commit()

    saved = session.query(Price).filter_by(ticker="btc_usd").one()

    assert saved.id is not None
    assert saved.ticker == "btc_usd"
    assert saved.price == Decimal("45000.50")
    assert saved.timestamp == 1700000000


def test_sync_price_repository_updates_existing_price(test_db_sync_session):
    session = test_db_sync_session
    repo = SyncPriceRepository(session)

    repo.save_price(
        ticker="btc_usd",
        price=Decimal("45000.50"),
        timestamp=1700000000,
    )
    session.commit()

    repo.save_price(
        ticker="btc_usd",
        price=Decimal("47000.25"),
        timestamp=1700000000,
    )
    session.commit()

    saved = session.query(Price).filter_by(ticker="btc_usd").all()

    assert len(saved) == 1
    assert saved[0].price == Decimal("47000.25")
