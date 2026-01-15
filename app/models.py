from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Numeric
from decimal import Decimal
from app.core.db import Base


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=8), nullable=False)
    timestamp: Mapped[int] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Price(ticker='{self.ticker}', price={self.price}, timestamp={self.timestamp}, created_at={self.created_at})>"