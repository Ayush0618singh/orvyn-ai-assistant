
export type AgentExecutionStatus =
  | "started"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface AgentExecution {
  id: string;
  status: AgentExecutionStatus;
  step_count: number;
  completed_steps: number;
  failure_category: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface AgentExecutionListResponse {
  items: AgentExecution[];
  total: number;
  limit: number;
  offset: number;
}

export type AgentExecutionFilter =
  | "all"
  | AgentExecutionStatus;
