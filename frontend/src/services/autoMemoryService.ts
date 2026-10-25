
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  AutoMemorySettings,
  UpdateAutoMemorySettingsPayload,
} from "@/types/autoMemory";

const AUTO_MEMORY_URL = `${API_URL}/auto-memory/settings`;

async function handleResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("Invalid response received from Auto Memory API.");
  }
}

export async function getAutoMemorySettings(
  signal?: AbortSignal
): Promise<AutoMemorySettings> {
  const response = await fetch(AUTO_MEMORY_URL, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });

  return handleResponse<AutoMemorySettings>(response);
}

export async function updateAutoMemorySettings(
  payload: UpdateAutoMemorySettingsPayload
): Promise<AutoMemorySettings> {
  const response = await fetch(AUTO_MEMORY_URL, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  return handleResponse<AutoMemorySettings>(response);
}
