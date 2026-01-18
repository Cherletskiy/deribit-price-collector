from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PriceResponse(BaseModel):
    ticker: str
    price: Decimal
    timestamp: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )
