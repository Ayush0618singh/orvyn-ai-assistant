
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
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw new Error("Limit must be between 1 and 100.");
  }

  if (!Number.isInteger(offset) || offset < 0) {
    throw new Error("Offset must be zero or greater.");
  }

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
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as AgentExecutionListResponse;
}

export async function getAgentExecution(
  executionId: string,
  signal?: AbortSignal
): Promise<AgentExecution> {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      executionId
    )
  ) {
    throw new Error("Invalid execution ID.");
  }

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
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as AgentExecution;
}
