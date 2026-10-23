
"""Read-only security audit for ORVYN chat approval links.

Run:
    python scripts/verify_chat_approval_links.py

Checks:
- Approval links point to existing conversations.
- Approval links point to existing approval records.
- Conversation owner matches link owner.
- Approval owner matches link owner.
- Reports linked approval lifecycle statuses.

Does not modify database records.
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import (  # noqa: E402
    AsyncSessionLocal,
    engine,
)
from app.models.chat_tool_approval_link import (  # noqa: E402
    ChatToolApprovalLink,
)
from app.models.conversation import (  # noqa: E402
    Conversation,
)
from app.models.tool_approval_record import (  # noqa: E402
    ToolApprovalRecord,
)


async def main() -> None:
    print("\nORVYN Chat Approval Security Audit")
    print("=" * 42)

    problems: list[str] = []
    statuses: Counter[str] = Counter()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                ChatToolApprovalLink,
                Conversation,
                ToolApprovalRecord,
            )
            .select_from(ChatToolApprovalLink)
            .outerjoin(
                Conversation,
                Conversation.id
                == ChatToolApprovalLink.conversation_id,
            )
            .outerjoin(
                ToolApprovalRecord,
                ToolApprovalRecord.id
                == ChatToolApprovalLink.approval_id,
            )
        )

        records = result.all()

        print(f"Linked approvals: {len(records)}")

        for link, conversation, approval in records:
            if conversation is None:
                problems.append(
                    f"{link.approval_id}: missing conversation"
                )
                continue

            if approval is None:
                problems.append(
                    f"{link.approval_id}: missing approval"
                )
                continue

            if conversation.user_id != link.user_id:
                problems.append(
                    f"{link.approval_id}: conversation "
                    "ownership mismatch"
                )

            if approval.user_id != link.user_id:
                problems.append(
                    f"{link.approval_id}: approval "
                    "ownership mismatch"
                )

            statuses[approval.status] += 1

            print(
                f"\nApproval: {approval.id}"
                f"\nConversation: {conversation.id}"
                f"\nTool: {approval.tool_name}"
                f"\nStatus: {approval.status}"
            )

    print("\nStatus summary:")

    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    if problems:
        print("\n[FAIL] Security inconsistencies:")

        for problem in problems:
            print(f"  - {problem}")

        raise SystemExit(1)

    print("\n[PASS] All stored links are consistent.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
