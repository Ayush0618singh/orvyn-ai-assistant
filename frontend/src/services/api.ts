import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
} from "@/types/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not configured. Add it to frontend/.env.local"
  );
}

export async function getBackendHealth(): Promise<HealthResponse> {
  const response = await fetch(
    `${API_URL}/health`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `Backend health request failed with status ${response.status}`
    );
  }

  return response.json();
}

export async function sendChatMessage(
  payload: ChatRequest
): Promise<ChatResponse> {
  const response = await fetch(
    `${API_URL}/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    let message =
      `Chat request failed with status ${response.status}`;

    try {
      const errorData =
        await response.json();

      if (
        typeof errorData?.detail ===
        "string"
      ) {
        message = errorData.detail;
      }
    } catch {
      // Keep the fallback error message.
    }

    throw new Error(message);
  }

  return response.json();
}