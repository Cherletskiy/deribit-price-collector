"""add unique constraint to prices

Revision ID: e8f1a2c4d6b7
Revises: bc1eb3694e77
Create Date: 2026-07-28 15:40:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e8f1a2c4d6b7"
down_revision: str | None = "bc1eb3694e77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_prices_ticker_timestamp",
        "prices",
        ["ticker", "timestamp"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_prices_ticker_timestamp", "prices", type_="unique")
