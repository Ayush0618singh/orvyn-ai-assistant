"""Add persistent agent execution audits.

Revision ID: 10je3a_audit
Revises: 14e9e8e0fccb
"""

from alembic import op
import sqlalchemy as sa


revision = "10je3a_audit"
down_revision = "14e9e8e0fccb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column(
            "completed_steps",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "failure_category",
            sa.String(40),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "step_count >= 1 AND step_count <= 5",
            name="ck_agent_audit_step_count",
        ),
        sa.CheckConstraint(
            "completed_steps >= 0 "
            "AND completed_steps <= step_count",
            name="ck_agent_audit_completed_steps",
        ),
        sa.CheckConstraint(
            "status IN "
            "('started', 'succeeded', 'failed', 'cancelled')",
            name="ck_agent_audit_status",
        ),
    )

    op.create_index(
        "ix_agent_audit_user_started",
        "agent_execution_audits",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_audit_user_started",
        table_name="agent_execution_audits",
    )

    op.drop_table("agent_execution_audits")