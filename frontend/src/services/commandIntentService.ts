
import type { ParsedCommand } from "@/types/commandAction";

export type CommandIntent =
  | "search_video"
  | "search_web"
  | "open_external_url"
  | "chat"
  | "unsupported";

export interface CommandIntentAnalysis {
  intent: CommandIntent;
  confidence: number;
  explanation: string;
  requiresUserConfirmation: boolean;
}

export function analyzeCommandIntent(
  command: ParsedCommand,
): CommandIntentAnalysis {
  switch (command.kind) {
    case "youtube_search":
      return {
        intent: "search_video",
        confidence: 0.98,
        explanation: "The command requests a YouTube search.",
        requiresUserConfirmation: false,
      };

    case "web_search":
      return {
        intent: "search_web",
        confidence: 0.98,
        explanation: "The command requests a web search.",
        requiresUserConfirmation: false,
      };

    case "open_url":
      return {
        intent: "open_external_url",
        confidence: 0.99,
        explanation: "The command requests navigation to an external URL.",
        requiresUserConfirmation: true,
      };

    case "chat_request":
      return {
        intent: "chat",
        confidence: 0.95,
        explanation: "The command should be handled by the chat interface.",
        requiresUserConfirmation: false,
      };

    default:
      return {
        intent: "unsupported",
        confidence: 0,
        explanation: "No supported command intent was identified.",
        requiresUserConfirmation: false,
      };
  }
}
