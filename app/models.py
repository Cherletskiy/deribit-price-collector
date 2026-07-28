from datetime import datetime
from decimal import Decimal

from sqlalchemy import Index, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ticker: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
    )

    timestamp: Mapped[int] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("ticker", "timestamp", name="uq_prices_ticker_timestamp"),
        Index("ix_prices_ticker_timestamp", "ticker", "timestamp"),
    )
