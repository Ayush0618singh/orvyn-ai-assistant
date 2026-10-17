
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  AgentExecution,
  AgentExecutionFilter,
  AgentExecutionListResponse,
} from "@/types/agentExecution";

interface ListExecutionOptions {
  status?: AgentExecutionFilter;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
}

export async function listAgentExecutions({
  status = "all",
  limit = 10,
  offset = 0,
  signal,
}: ListExecutionOptions = {}): Promise<AgentExecutionListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (status !== "all") {
    params.set("status", status);
  }

  const response = await fetch(
    `${API_URL}/agent-executions?${params.toString()}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}

export async function getAgentExecution(
  executionId: string,
  signal?: AbortSignal
): Promise<AgentExecution> {
  const response = await fetch(
    `${API_URL}/agent-executions/${encodeURIComponent(executionId)}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}
