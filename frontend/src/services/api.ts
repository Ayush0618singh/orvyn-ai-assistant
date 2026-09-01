import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
} from "@/types/api";


export const API_URL =
  process.env.NEXT_PUBLIC_API_URL;


if (!API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not configured."
  );
}


export type ChatStreamMetaEvent = {
  type: "meta";
  conversation_id: string;
  user_message_id: string;
  provider: string;
  model: string;
};


export type ChatStreamDeltaEvent = {
  type: "delta";
  content: string;
};


export type ChatStreamDoneEvent = {
  type: "done";
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string;
  provider: string;
  model: string;
};


export type ChatStreamErrorEvent = {
  type: "error";
  message: string;
};


export type ChatStreamEvent =
  | ChatStreamMetaEvent
  | ChatStreamDeltaEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent;


export async function parseApiError(
  response: Response
): Promise<string> {
  try {
    const data = await response.json();

    if (
      typeof data?.detail === "string"
    ) {
      return data.detail;
    }
  } catch {
    // Use fallback message below.
  }

  return (
    `Request failed with status ${response.status}`
  );
}


export async function getBackendHealth(): Promise<HealthResponse> {
  const response = await fetch(
    `${API_URL}/health`,
    {
      method: "GET",
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


/*
 * Keep the existing non-streaming API.
 * This remains useful for testing and fallback.
 */
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
      credentials: "include",
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


/*
 * Streaming chat API.
 *
 * Backend sends NDJSON:
 *
 * {"type":"meta", ...}
 * {"type":"delta", ...}
 * {"type":"delta", ...}
 * {"type":"done", ...}
 */
export async function* streamChatMessage(
  payload: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(
    `${API_URL}/chat/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
        Accept:
          "application/x-ndjson",
      },
      credentials: "include",
      body: JSON.stringify(payload),
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }


  if (!response.body) {
    throw new Error(
      "Streaming response body is unavailable."
    );
  }


  const reader =
    response.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";


  try {
    while (true) {
      const {
        value,
        done,
      } = await reader.read();


      if (done) {
        break;
      }


      buffer += decoder.decode(
        value,
        {
          stream: true,
        }
      );


      const lines =
        buffer.split("\n");


      buffer =
        lines.pop() ?? "";


      for (const line of lines) {
        const cleanedLine =
          line.trim();


        if (!cleanedLine) {
          continue;
        }


        let event: ChatStreamEvent;


        try {
          event = JSON.parse(
            cleanedLine
          ) as ChatStreamEvent;
        } catch {
          throw new Error(
            "Received an invalid streaming response from ORVYN."
          );
        }


        yield event;
      }
    }


    buffer += decoder.decode();


    const finalLine =
      buffer.trim();


    if (finalLine) {
      try {
        yield JSON.parse(
          finalLine
        ) as ChatStreamEvent;
      } catch {
        throw new Error(
          "Received an invalid final streaming response from ORVYN."
        );
      }
    }

  } finally {
    reader.releaseLock();
  }
}