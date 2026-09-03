import type {
  CreateMemoryPayload,
  Memory,
  UpdateMemoryPayload,
} from "@/types/memory";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";


async function handleResponse<T>(
  response: Response
): Promise<T> {
  if (response.status === 401) {
    throw new Error(
      "Your session has expired. Please log in again."
    );
  }

  if (!response.ok) {
    let message =
      "Something went wrong while processing the memory request.";

    try {
      const data = await response.json();

      if (
        typeof data?.detail === "string"
      ) {
        message = data.detail;
      }
    } catch {
      // Ignore malformed error response.
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}


export async function getMemories(
  options?: {
    memoryType?: string;
    activeOnly?: boolean;
  }
): Promise<Memory[]> {
  const params =
    new URLSearchParams();

  if (options?.memoryType) {
    params.set(
      "memory_type",
      options.memoryType
    );
  }

  if (
    options?.activeOnly !==
    undefined
  ) {
    params.set(
      "active_only",
      String(
        options.activeOnly
      )
    );
  }

  const query =
    params.toString();

  const response = await fetch(
    `${API_BASE_URL}/memories${
      query ? `?${query}` : ""
    }`,
    {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    }
  );

  return handleResponse<Memory[]>(
    response
  );
}


export async function createMemory(
  payload: CreateMemoryPayload
): Promise<Memory> {
  const response = await fetch(
    `${API_BASE_URL}/memories`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type":
          "application/json",
        Accept:
          "application/json",
      },
      body: JSON.stringify(
        payload
      ),
    }
  );

  return handleResponse<Memory>(
    response
  );
}


export async function updateMemory(
  memoryId: string,
  payload: UpdateMemoryPayload
): Promise<Memory> {
  const response = await fetch(
    `${API_BASE_URL}/memories/${memoryId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type":
          "application/json",
        Accept:
          "application/json",
      },
      body: JSON.stringify(
        payload
      ),
    }
  );

  return handleResponse<Memory>(
    response
  );
}


export async function deleteMemory(
  memoryId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/memories/${memoryId}`,
    {
      method: "DELETE",
      credentials: "include",
      headers: {
        Accept:
          "application/json",
      },
    }
  );

  await handleResponse<void>(
    response
  );
}