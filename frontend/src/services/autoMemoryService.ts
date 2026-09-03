import type {
  AutoMemorySettings,
  UpdateAutoMemorySettingsPayload,
} from "@/types/autoMemory";


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
      "Something went wrong while processing the automatic memory request.";

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

  return response.json();
}


export async function getAutoMemorySettings():
Promise<AutoMemorySettings> {
  const response = await fetch(
    `${API_BASE_URL}/auto-memory/settings`,
    {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    }
  );

  return handleResponse<AutoMemorySettings>(
    response
  );
}


export async function updateAutoMemorySettings(
  payload: UpdateAutoMemorySettingsPayload
): Promise<AutoMemorySettings> {
  const response = await fetch(
    `${API_BASE_URL}/auto-memory/settings`,
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

  return handleResponse<AutoMemorySettings>(
    response
  );
}