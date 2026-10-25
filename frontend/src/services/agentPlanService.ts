
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  AgentPlanDetail,
  AgentPlanListResponse,
  CreateAgentPlanRequest,
} from "@/types/agentPlan";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function validateUuid(
  value: string,
  fieldName: string
): void {
  if (!UUID_PATTERN.test(value)) {
    throw new Error(`Invalid ${fieldName}.`);
  }
}

async function parseResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("ORVYN returned an invalid API response.");
  }
}

export async function getAgentPlans(
  limit = 20,
  offset = 0,
  signal?: AbortSignal
): Promise<AgentPlanListResponse> {
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

  const response = await fetch(
    `${API_URL}/agent-plans?${params.toString()}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  return parseResponse<AgentPlanListResponse>(response);
}

export async function getAgentPlan(
  planId: string,
  signal?: AbortSignal
): Promise<AgentPlanDetail> {
  validateUuid(planId, "plan ID");

  const response = await fetch(
    `${API_URL}/agent-plans/${encodeURIComponent(planId)}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  return parseResponse<AgentPlanDetail>(response);
}

export async function createAgentPlan(
  payload: CreateAgentPlanRequest
): Promise<AgentPlanDetail> {
  validateUuid(payload.conversation_id, "conversation ID");

  const request = payload.request.trim();

  if (request.length === 0 || request.length > 8192) {
    throw new Error("Task must contain 1–8192 characters.");
  }

  const response = await fetch(`${API_URL}/agent-plans`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      conversation_id: payload.conversation_id,
      request,
    }),
    cache: "no-store",
  });

  return parseResponse<AgentPlanDetail>(response);
}
