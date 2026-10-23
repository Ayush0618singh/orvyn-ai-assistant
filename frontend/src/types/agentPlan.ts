
export type AgentPlanStatus =
  | "planned"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentStepStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export interface AgentPlanSummary {
  id: string;
  conversation_id: string;
  original_request: string;
  status: AgentPlanStatus;
  created_at: string;
}

export interface AgentStep {
  id: string;
  position: number;
  kind: string;
  description: string;
  depends_on: string[];
  requires_approval: boolean;
  status: AgentStepStatus;
}

export interface AgentPlanDetail
  extends AgentPlanSummary {
  steps: AgentStep[];
}

export interface AgentPlanListResponse {
  items: AgentPlanSummary[];
  total: number;
}

export interface CreateAgentPlanRequest {
  conversation_id: string;
  request: string;
}
