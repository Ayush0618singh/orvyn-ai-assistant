"""add message status

Revision ID: 6c1949066538
Revises: 61f80b731f0d
Create Date: 2026-09-01 02:28:53.851902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c1949066538'
down_revision: Union[str, Sequence[str], None] = '61f80b731f0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "status",
            sa.String(
                length=20
            ),
            nullable=False,
            server_default="completed",
        ),
    )

    op.create_index(
        op.f(
            "ix_messages_status"
        ),
        "messages",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_messages_status"
        ),
        table_name="messages",
    )

    op.drop_column(
        "messages",
        "status",
    )
