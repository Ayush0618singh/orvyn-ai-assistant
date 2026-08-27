export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  response: string;
  model: string;
  provider: string;
}

export interface ApiError {
  message: string;
}