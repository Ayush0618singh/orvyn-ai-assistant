export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ChatRequest {
  message: string;
  conversation_id: string | null;
  attachment_ids?: string[];
}

export interface ChatResponse {
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string;
  response: string;
  model: string;
  provider: string;
}

export interface ApiError {
  message: string;
}