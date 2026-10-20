
"""Add heartbeat timestamp for agent execution recovery.

Revision ID: 10je7c_heartbeat
Revises: 10je3a_audit
"""

from alembic import op
import sqlalchemy as sa


revision = "10je7c_heartbeat"
down_revision = "10je3a_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table(
        "agent_execution_audits"
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "last_heartbeat_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.create_index(
        "ix_agent_audit_status_heartbeat",
        "agent_execution_audits",
        ["status", "last_heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_audit_status_heartbeat",
        table_name="agent_execution_audits",
    )

    with op.batch_alter_table(
        "agent_execution_audits"
    ) as batch_op:
        batch_op.drop_column("last_heartbeat_at")
