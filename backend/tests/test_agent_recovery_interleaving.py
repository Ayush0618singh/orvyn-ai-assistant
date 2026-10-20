
"""ORVYN Phase 10J-E8C.

Verify a heartbeat committed after stale candidate selection
prevents recovery from incorrectly finalizing an active audit.

Uses real SQLite database connections and SQLAlchemy sessions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User
from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
)


@pytest.mark.asyncio
async def test_fresh_heartbeat_after_selection_blocks_recovery(
    tmp_path,
):
    database_path = tmp_path / "interleaving.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        connect_args={"timeout": 10},
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        user_id = uuid4()
        audit_id = uuid4()

        now = datetime.now(timezone.utc)

        async with factory() as session:
            session.add(
                User(
                    id=str(user_id),
                    email=f"{user_id}@example.test",
                    password_hash="test-hash",
                )
            )

            session.add(
                AgentExecutionAudit(
                    id=str(audit_id),
                    user_id=str(user_id),
                    status="started",
                    step_count=1,
                    completed_steps=0,
                    started_at=now - timedelta(hours=2),
                    last_heartbeat_at=None,
                )
            )

            await session.commit()

        selected = asyncio.Event()
        resume_recovery = asyncio.Event()

        # Intercept the recovery session after its SELECT.
        original_execute = None

        async with factory() as recovery_session:
            original_execute = recovery_session.execute

            async def controlled_execute(statement, *args, **kwargs):
                result = await original_execute(
                    statement,
                    *args,
                    **kwargs,
                )

                if getattr(statement, "is_select", False):
                    selected.set()

                    await asyncio.wait_for(
                        resume_recovery.wait(),
                        timeout=5,
                    )

                return result

            recovery_session.execute = controlled_execute

            recovery_task = asyncio.create_task(
                AgentExecutionRecoveryService(
                    recovery_session
                ).recover_stale(
                    stale_after_minutes=60,
                    dry_run=False,
                )
            )

            await asyncio.wait_for(
                selected.wait(),
                timeout=5,
            )

            # Another session commits a fresh heartbeat while
            # recovery is paused between SELECT and UPDATE.
            async with factory() as heartbeat_session:
                audit = await heartbeat_session.get(
                    AgentExecutionAudit,
                    str(audit_id),
                )

                audit.last_heartbeat_at = datetime.now(
                    timezone.utc
                )

                await heartbeat_session.commit()

            resume_recovery.set()

            result = await asyncio.wait_for(
                recovery_task,
                timeout=5,
            )

        assert result.examined == 1
        assert result.recovered == 0

        async with factory() as session:
            audit = await session.get(
                AgentExecutionAudit,
                str(audit_id),
            )

        assert audit.status == "started"
        assert audit.last_heartbeat_at is not None

    finally:
        await engine.dispose()
