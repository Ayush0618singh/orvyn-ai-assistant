import type {
  Attachment,
} from "@/types/attachment";

import type {
  RAGSource,
} from "@/types/rag";

import type {
  WebSource,
} from "@/types/webSource";


export interface ConversationSummary {
  id: string;

  title: string;

  created_at: string;

  updated_at: string;
}


export interface ConversationMessage {
  id: string;

  role:
    | "user"
    | "assistant";

  content: string;

  provider:
    | string
    | null;

  model:
    | string
    | null;

  status:
    | "pending"
    | "streaming"
    | "completed"
    | "failed"
    | "cancelled";

  created_at: string;

  attachments: Attachment[];

  sources: RAGSource[];

  web_sources: WebSource[];
}


export interface ConversationDetail {
  id: string;

  title: string;

  created_at: string;

  updated_at: string;

  messages: ConversationMessage[];
}