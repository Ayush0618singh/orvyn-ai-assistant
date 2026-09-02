import type {
  Attachment,
} from "@/types/attachment";

import type {
  RAGSource,
} from "@/types/rag";


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

  provider?: string;

  model?: string;

  status?: ChatMessageStatus;

  attachments?: Attachment[];

  sources?: RAGSource[];
}