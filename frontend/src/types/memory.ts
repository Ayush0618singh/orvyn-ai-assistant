export type MemoryType =
  | "fact"
  | "preference"
  | "instruction"
  | "note"
  | "profile";

export interface Memory {
  id: string;
  user_id: string;
  source_message_id: string | null;
  memory_type: MemoryType;
  content: string;
  importance: number;
  is_active: boolean;
  embedding_model: string | null;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

export interface UpdateMemoryPayload {
  content?: string;
  memory_type?: MemoryType;
  importance?: number;
  is_active?: boolean;
}

export interface CreateMemoryPayload {
  content: string;
  memory_type: MemoryType;
  importance: number;
}