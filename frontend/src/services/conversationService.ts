
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  ConversationDetail,
  ConversationSummary,
} from "@/types/conversation";

import type {
  ChatMessage,
} from "@/types/chat";

export async function getConversations(): Promise<
  ConversationSummary[]
> {
  const response = await fetch(
    `${API_URL}/conversations`,
    {
      credentials: "include",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}

export async function getConversation(
  conversationId: string
): Promise<ConversationDetail> {
  const response = await fetch(
    `${API_URL}/conversations/${conversationId}`,
    {
      credentials: "include",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}

export async function deleteConversation(
  conversationId: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/conversations/${conversationId}`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );

  if (
    !response.ok &&
    response.status !== 204
  ) {
    throw new Error(
      await parseApiError(response)
    );
  }
}

export async function renameConversation(
  conversationId: string,
  title: string
): Promise<ConversationSummary> {
  const response = await fetch(
    `${API_URL}/conversations/${conversationId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        title,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}

export async function createConversation(
  title = "New Chat"
): Promise<ConversationSummary> {
  const response = await fetch(
    `${API_URL}/conversations`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json() as Promise<
    ConversationSummary
  >;
}

/**
 * Persist the original user request for a file action.
 *
 * Does not invoke AI, create approvals or execute tools.
 */
export async function createConversationActionMessage(
  conversationId: string,
  content: string
): Promise<ChatMessage> {
  const response = await fetch(
    `${API_URL}/conversations/${encodeURIComponent(
      conversationId
    )}/action-messages`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        content,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  const saved = await response.json();

  return {
    id: saved.id,
    role: saved.role,
    content: saved.content,
    status: saved.status,
    provider: saved.provider ?? undefined,
    model: saved.model ?? undefined,
    attachments: saved.attachments ?? [],
    sources: saved.sources ?? [],
    web_sources: saved.web_sources ?? [],
  } as ChatMessage;
}
