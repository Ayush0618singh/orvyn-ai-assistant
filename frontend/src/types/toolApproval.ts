
export type ApprovalStatus =
  | "pending"
  | "approved"
  | "denied"
  | "consumed"
  | "expired";

export interface ToolApproval {
  id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  risk_level: string;
  status: ApprovalStatus;
  created_at: string;
  expires_at: string;
  decided_at: string | null;
  consumed_at: string | null;
}

export interface ToolApprovalListResponse {
  items: ToolApproval[];
  total: number;
  limit: number;
  offset: number;
}

export interface ToolApprovalDecisionResponse {
  id: string;
  status: ApprovalStatus;
  decided_at: string;
}

export interface ToolExecutionResponse {
  execution_id: string;
  tool_name: string;
  status: string;
  output: unknown;
  error: {
    code: string;
    message: string;
    retryable: boolean;
  } | null;
}

export interface WorkspaceFileRequest {
  filename: string;
  content: string;
}

export interface ChatWorkspaceFileRequest
  extends WorkspaceFileRequest {
  conversation_id: string;
  message_id?: string;
}

export interface ApprovalMessageLink {
  approval_id: string;
  conversation_id: string;
  message_id: string | null;
}

export interface ApprovalMessageLinksResponse {
  items: ApprovalMessageLink[];
  total: number;
}

export type ApprovalFilter =
  | "all"
  | ApprovalStatus;
