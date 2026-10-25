
export type CommandActionKind =
  | "youtube_search"
  | "web_search"
  | "google_images"
  | "open_url"
  | "chat_request"
  | "unsupported";

export type CommandActionStatus =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "blocked";

export interface ParsedCommand {
  id: string;
  originalText: string;
  kind: CommandActionKind;
  title: string;
  description: string;
  query?: string;
  url?: string;
  requiresConfirmation: boolean;
}

export interface CommandActionResult {
  commandId: string;
  status: CommandActionStatus;
  message: string;
  completedAt: string;
}

export interface CommandHistoryEntry {
  id: string;
  command: string;
  action: string;
  status: CommandActionStatus;
  message: string;
  createdAt: string;
}
