"""day end per account

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 0 = the day ends at midnight, as before; existing accounts keep that
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("day_end_hour", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("day_end_hour")
