
import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  ApprovalFilter,
  ToolApproval,
  ToolApprovalDecisionResponse,
  ToolApprovalListResponse,
  ToolExecutionResponse,
  WorkspaceFileRequest,
} from "@/types/toolApproval";

const READ_URL =
  `${API_URL}/tool-approvals`;

const ACTION_URL =
  "/api/tool-approvals";

async function readResponse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json() as Promise<T>;
}

export async function listToolApprovals(
  options: {
    status?: ApprovalFilter;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  } = {}
): Promise<ToolApprovalListResponse> {
  const {
    status = "all",
    limit = 20,
    offset = 0,
    signal,
  } = options;

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (status !== "all") {
    params.set("status", status);
  }

  const response = await fetch(
    `${READ_URL}?${params.toString()}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  return readResponse<ToolApprovalListResponse>(
    response
  );
}

export async function getToolApproval(
  approvalId: string,
  signal?: AbortSignal
): Promise<ToolApproval> {
  const response = await fetch(
    `${READ_URL}/${encodeURIComponent(approvalId)}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal,
    }
  );

  return readResponse<ToolApproval>(response);
}

export async function requestWorkspaceFileApproval(
  payload: WorkspaceFileRequest
): Promise<ToolApproval> {
  const response = await fetch(
    `${ACTION_URL}/workspace-file`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );

  return readResponse<ToolApproval>(response);
}

async function decideToolApproval(
  approvalId: string,
  action: "approve" | "deny"
): Promise<ToolApprovalDecisionResponse> {
  const response = await fetch(
    `${ACTION_URL}/${encodeURIComponent(approvalId)}/${action}`,
    {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    }
  );

  return readResponse<ToolApprovalDecisionResponse>(
    response
  );
}

export async function approveToolApproval(
  approvalId: string
): Promise<ToolApprovalDecisionResponse> {
  return decideToolApproval(
    approvalId,
    "approve"
  );
}

export async function denyToolApproval(
  approvalId: string
): Promise<ToolApprovalDecisionResponse> {
  return decideToolApproval(
    approvalId,
    "deny"
  );
}

export async function executeToolApproval(
  approvalId: string
): Promise<ToolExecutionResponse> {
  const response = await fetch(
    `${ACTION_URL}/${encodeURIComponent(approvalId)}/execute`,
    {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    }
  );

  return readResponse<ToolExecutionResponse>(
    response
  );
}
