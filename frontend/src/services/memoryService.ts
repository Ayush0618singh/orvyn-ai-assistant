
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  CreateMemoryPayload,
  Memory,
  UpdateMemoryPayload,
} from "@/types/memory";

const MEMORY_URL = `${API_URL}/memories`;

async function handleResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("Invalid response received from Memory API.");
  }
}

export async function getMemories(
  options?: {
    memoryType?: string;
    activeOnly?: boolean;
    signal?: AbortSignal;
  }
): Promise<Memory[]> {
  const params = new URLSearchParams();

  if (options?.memoryType) {
    params.set("memory_type", options.memoryType);
  }

  if (options?.activeOnly !== undefined) {
    params.set("active_only", String(options.activeOnly));
  }

  const query = params.toString();

  const response = await fetch(
    `${MEMORY_URL}${query ? `?${query}` : ""}`,
    {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: options?.signal,
    }
  );

  return handleResponse<Memory[]>(response);
}

export async function createMemory(
  payload: CreateMemoryPayload
): Promise<Memory> {
  const content = payload.content.trim();

  if (!content || content.length > 8192) {
    throw new Error("Memory content must contain 1–8192 characters.");
  }

  if (!Number.isFinite(payload.importance) ||
      payload.importance < 0 ||
      payload.importance > 1) {
    throw new Error("Memory importance must be between 0 and 1.");
  }

  const response = await fetch(MEMORY_URL, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      ...payload,
      content,
    }),
    cache: "no-store",
  });

  return handleResponse<Memory>(response);
}

export async function updateMemory(
  memoryId: string,
  payload: UpdateMemoryPayload
): Promise<Memory> {
  if (!memoryId.trim()) {
    throw new Error("Memory ID is required.");
  }

  const body: UpdateMemoryPayload = { ...payload };

  if (body.content !== undefined) {
    body.content = body.content.trim();

    if (!body.content || body.content.length > 8192) {
      throw new Error("Memory content must contain 1–8192 characters.");
    }
  }

  if (body.importance !== undefined &&
      (!Number.isFinite(body.importance) ||
       body.importance < 0 ||
       body.importance > 1)) {
    throw new Error("Memory importance must be between 0 and 1.");
  }

  const response = await fetch(
    `${MEMORY_URL}/${encodeURIComponent(memoryId)}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    }
  );

  return handleResponse<Memory>(response);
}

export async function deleteMemory(
  memoryId: string
): Promise<void> {
  if (!memoryId.trim()) {
    throw new Error("Memory ID is required.");
  }

  const response = await fetch(
    `${MEMORY_URL}/${encodeURIComponent(memoryId)}`,
    {
      method: "DELETE",
      credentials: "include",
      headers: { Accept: "application/json" },
      cache: "no-store",
    }
  );

  await handleResponse<void>(response);
}
