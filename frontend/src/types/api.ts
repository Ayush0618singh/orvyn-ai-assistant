import type {
  RAGSource,
} from "@/types/rag";
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
  document_ids?: string[];
}

export interface ChatResponse {
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string;
  response: string;
  model: string;
  provider: string;
  sources: RAGSource[];
}

export interface ApiError {
  message: string;
}