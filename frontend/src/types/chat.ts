export type ChatRole =
  | "user"
  | "assistant";


export type ChatMessageStatus =
  | "pending"
  | "streaming"
  | "completed"
  | "failed"
  | "cancelled";


export interface ChatMessage {
  id: string;

  role: ChatRole;

  content: string;

  model?: string;

  provider?: string;

  status?: ChatMessageStatus;
}