
import type {
  AgentPlanDetail,
  AgentPlanListResponse,
  CreateAgentPlanRequest,
} from "@/types/agentPlan";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function validateUuid(
  value: string,
  fieldName: string
): void {
  if (!UUID_PATTERN.test(value)) {
    throw new Error(
      `Invalid ${fieldName}.`
    );
  }
}

async function parseResponse<T>(
  response: Response
): Promise<T> {
  const payload: unknown =
    await response.json().catch(
      () => null
    );

  if (!response.ok) {
    let detail = (
      `Request failed (${response.status}).`
    );

    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload
    ) {
      const value = (
        payload as { detail: unknown }
      ).detail;

      if (typeof value === "string") {
        detail = value;
      }
    }

    throw new Error(detail);
  }

  return payload as T;
}

export async function getAgentPlans(
  limit = 20,
  offset = 0
): Promise<AgentPlanListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  const response = await fetch(
    `${API_URL}/agent-plans?${params}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  return parseResponse<AgentPlanListResponse>(
    response
  );
}

export async function getAgentPlan(
  planId: string
): Promise<AgentPlanDetail> {
  validateUuid(planId, "plan ID");

  const response = await fetch(
    `${API_URL}/agent-plans/${encodeURIComponent(
      planId
    )}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  return parseResponse<AgentPlanDetail>(
    response
  );
}

export async function createAgentPlan(
  payload: CreateAgentPlanRequest
): Promise<AgentPlanDetail> {
  validateUuid(
    payload.conversation_id,
    "conversation ID"
  );

  const request = payload.request.trim();

  if (
    request.length === 0 ||
    request.length > 8192
  ) {
    throw new Error(
      "Task must contain 1–8192 characters."
    );
  }

  const response = await fetch(
    `${API_URL}/agent-plans`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        conversation_id:
          payload.conversation_id,
        request,
      }),
      cache: "no-store",
    }
  );

  return parseResponse<AgentPlanDetail>(
    response
  );
}
