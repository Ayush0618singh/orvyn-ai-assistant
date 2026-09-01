import type {
  ChatMessageStatus,
} from "@/types/chat";


export interface ConversationSummary {
  id: string;

  title: string;

  created_at: string;

  updated_at: string;
}


export interface StoredMessage {
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
    ChatMessageStatus;

  created_at: string;
}


export interface ConversationDetail {
  id: string;

  title: string;

  created_at: string;

  updated_at: string;

  messages:
    StoredMessage[];
}