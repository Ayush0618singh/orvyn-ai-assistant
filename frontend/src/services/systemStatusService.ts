
import {
  API_URL,
  parseApiError,
} from "@/services/api";

export interface SystemResources {
  available: boolean;
  cpu_percent: number | null;
  memory_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
}

export interface SystemStatus {
  application: string;
  status: "online" | "degraded";
  database: "online" | "unavailable";
  uptime_seconds: number;
  python_version: string;
  platform: string;
  resources: SystemResources;
  metrics_scope: "host" | "unavailable";
  timestamp: string;
}

export async function getSystemStatus(
  signal?: AbortSignal,
): Promise<SystemStatus> {
  const response = await fetch(
    `${API_URL}/system-status`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<SystemStatus>;
}
