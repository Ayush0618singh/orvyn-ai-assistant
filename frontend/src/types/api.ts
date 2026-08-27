export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export type ApiChatRole =
  | "user"
  | "assistant";

export interface ApiChatMessage {
  role: ApiChatRole;
  content: string;
}

export interface ChatRequest {
  messages: ApiChatMessage[];
}

export interface ChatResponse {
  response: string;
  model: string;
  provider: string;
}

export interface ApiError {
  message: string;
}