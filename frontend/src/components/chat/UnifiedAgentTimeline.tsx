
"use client";

import { useMemo } from "react";

import MessageBubble from "@/components/chat/MessageBubble";
import ChatFileApprovalCard from "@/components/chat/ChatFileApprovalCard";

import type { ChatMessage } from "@/types/chat";
import type {
  ApprovalMessageLink,
  ToolApproval,
} from "@/types/toolApproval";

interface UnifiedAgentTimelineProps {
  messages: ChatMessage[];
  approvals: ToolApproval[];
  approvalLinks: ApprovalMessageLink[];
}

type TimelineItem =
  | {
      kind: "message";
      id: string;
      message: ChatMessage;
    }
  | {
      kind: "approval";
      id: string;
      approval: ToolApproval;
    };

export default function UnifiedAgentTimeline({
  messages,
  approvals,
  approvalLinks,
}: UnifiedAgentTimelineProps) {
  const timeline = useMemo(() => {
    const items: TimelineItem[] = [];

    const messageIds = new Set(
      messages.map((message) => message.id)
    );

    const approvalById = new Map(
      approvals.map((approval) => [
        approval.id,
        approval,
      ])
    );

    const linkedApprovals = new Map<
      string,
      ToolApproval[]
    >();

    const renderedApprovalIds = new Set<string>();

    for (const link of approvalLinks) {
      if (
        !link.message_id ||
        !messageIds.has(link.message_id)
      ) {
        continue;
      }

      const approval = approvalById.get(
        link.approval_id
      );

      if (!approval) {
        continue;
      }

      const existing =
        linkedApprovals.get(link.message_id) ?? [];

      existing.push(approval);

      linkedApprovals.set(
        link.message_id,
        existing
      );
    }

    for (const message of messages) {
      items.push({
        kind: "message",
        id: `message:${message.id}`,
        message,
      });

      const relatedApprovals =
        linkedApprovals.get(message.id) ?? [];

      for (const approval of relatedApprovals) {
        if (renderedApprovalIds.has(approval.id)) {
          continue;
        }

        items.push({
          kind: "approval",
          id: `approval:${approval.id}`,
          approval,
        });

        renderedApprovalIds.add(approval.id);
      }
    }

    // Legacy approvals have no message_id.
    // Never guess which user message owns them.
    // Keep them visible in their own section.
    for (const approval of approvals) {
      if (renderedApprovalIds.has(approval.id)) {
        continue;
      }

      items.push({
        kind: "approval",
        id: `approval:${approval.id}`,
        approval,
      });

      renderedApprovalIds.add(approval.id);
    }

    return items;
  }, [messages, approvals, approvalLinks]);

  return (
    <>
      {timeline.map((item) => {
        if (item.kind === "message") {
          return (
            <MessageBubble
              key={item.id}
              message={item.message}
            />
          );
        }

        return (
          <ChatFileApprovalCard
            key={item.id}
            initialApproval={item.approval}
          />
        );
      })}
    </>
  );
}
