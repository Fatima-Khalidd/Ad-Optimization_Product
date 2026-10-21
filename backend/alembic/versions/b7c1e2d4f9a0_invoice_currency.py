"""invoice currency and exchange rate

Revision ID: b7c1e2d4f9a0
Revises: dabea491354c
Create Date: 2026-10-22 00:00:00.000000

Billing moves to USD. Existing invoices were drafted in PKR, so the server default keeps
them "PKR" with no rate; the app writes "USD" and the rate on every new invoice.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1e2d4f9a0"
down_revision: str | Sequence[str] | None = "dabea491354c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("currency", sa.String(length=3), server_default="PKR", nullable=False)
        )
        batch_op.add_column(
            sa.Column("pkr_per_usd", sa.Numeric(precision=10, scale=4), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.drop_column("pkr_per_usd")
        batch_op.drop_column("currency")
