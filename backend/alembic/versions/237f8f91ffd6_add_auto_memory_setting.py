"""add auto memory setting

Revision ID: 237f8f91ffd6
Revises: e632c817fb0f
Create Date: 2026-09-03 21:50:29.934171

"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "237f8f91ffd6"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "e632c817fb0f"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    """Add the automatic-memory opt-in setting."""

    op.add_column(
        "users",
        sa.Column(
            "auto_memory_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Remove the automatic-memory opt-in setting."""

    op.drop_column(
        "users",
        "auto_memory_enabled",
    )