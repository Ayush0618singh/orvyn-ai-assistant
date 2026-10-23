
import type {
  ApprovalMessageLinksResponse,
  ChatWorkspaceFileRequest,
  ToolApproval,
  ToolApprovalListResponse,
} from "@/types/toolApproval";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function parseResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    let message =
      `Request failed (${response.status})`;

    try {
      const body: unknown =
        await response.json();

      if (
        body !== null &&
        typeof body === "object" &&
        "detail" in body
      ) {
        const detail = body.detail;

        if (
          typeof detail === "string"
        ) {
          message = detail;
        }
      }
    } catch {
      // Preserve HTTP status error.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function requireUuid(
  value: string,
  fieldName: string
): void {
  if (
    !UUID_PATTERN.test(value)
  ) {
    throw new Error(
      `Invalid ${fieldName}.`
    );
  }
}

/**
 * Create a conversation-linked approval request.
 *
 * This never approves or executes the tool.
 */
export async function requestChatWorkspaceFileApproval(
  payload: ChatWorkspaceFileRequest
): Promise<ToolApproval> {
  requireUuid(
    payload.conversation_id,
    "conversation ID"
  );

  if (
    payload.message_id !== undefined
  ) {
    requireUuid(
      payload.message_id,
      "message ID"
    );
  }

  const response = await fetch(
    "/api/tool-approvals/chat/workspace-file",
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        payload
      ),
      cache: "no-store",
    }
  );

  return parseResponse<ToolApproval>(
    response
  );
}

/**
 * Existing conversation approval history.
 */
export async function getConversationToolApprovals(
  conversationId: string,
  limit = 100,
  offset = 0
): Promise<ToolApprovalListResponse> {
  requireUuid(
    conversationId,
    "conversation ID"
  );

  const query =
    new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });

  const response = await fetch(
    `${API_URL}/chat-tool-approvals/conversations/${encodeURIComponent(
      conversationId
    )}?${query.toString()}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  return parseResponse<ToolApprovalListResponse>(
    response
  );
}

/**
 * Return the exact originating message
 * for each linked approval.
 *
 * Older approvals may have message_id=null.
 */
export async function getConversationApprovalMessageLinks(
  conversationId: string
): Promise<ApprovalMessageLinksResponse> {
  requireUuid(
    conversationId,
    "conversation ID"
  );

  const response = await fetch(
    `${API_URL}/chat-tool-approvals/conversations/${encodeURIComponent(
      conversationId
    )}/message-links`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  return parseResponse<ApprovalMessageLinksResponse>(
    response
  );
}
