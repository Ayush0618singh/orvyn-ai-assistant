import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  ConversationDetail,
  ConversationSummary,
} from "@/types/conversation";


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
        "Content-Type":
          "application/json",
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