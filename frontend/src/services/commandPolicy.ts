import type { ParsedCommand } from "@/types/commandAction";
import { validateExternalUrl } from "@/utils/commandSecurity";

export interface CommandPolicyDecision {
  allowed: boolean;
  requiresConfirmation: boolean;
  reason?: string;
}

const MAX_COMMAND_LENGTH = 1000;
const MAX_QUERY_LENGTH = 500;
const MAX_URL_LENGTH = 2048;

function deny(reason: string): CommandPolicyDecision {
  return {
    allowed: false,
    requiresConfirmation: false,
    reason,
  };
}

function allow(
  requiresConfirmation = false,
): CommandPolicyDecision {
  return {
    allowed: true,
    requiresConfirmation,
  };
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function evaluateCommandPolicy(
  command: ParsedCommand,
): CommandPolicyDecision {
  if (!command || typeof command !== "object") {
    return deny("The command is missing or invalid.");
  }

  if (
    !isNonEmptyString(command.id) ||
    !isNonEmptyString(command.originalText)
  ) {
    return deny("The command is incomplete.");
  }

  if (command.originalText.length > MAX_COMMAND_LENGTH) {
    return deny(
      `Commands must be ${MAX_COMMAND_LENGTH} characters or fewer.`,
    );
  }

  if (
    typeof command.requiresConfirmation !== "boolean" ||
    !isNonEmptyString(command.title) ||
    !isNonEmptyString(command.description)
  ) {
    return deny("The command metadata is invalid.");
  }

  switch (command.kind) {
    case "youtube_search":
    case "web_search":
    case "google_images": {
      if (!isNonEmptyString(command.query)) {
        return deny("A search query is required.");
      }

      if (command.query.length > MAX_QUERY_LENGTH) {
        return deny(
          `Search queries must be ${MAX_QUERY_LENGTH} characters or fewer.`,
        );
      }

      if (command.url !== undefined) {
        return deny(
          "Search commands cannot contain an external destination URL.",
        );
      }

      // Search actions use the existing supported search handlers.
      return allow(command.requiresConfirmation);
    }

    case "open_url": {
      if (!isNonEmptyString(command.url)) {
        return deny("A destination URL is required.");
      }

      if (command.url.length > MAX_URL_LENGTH) {
        return deny("The destination URL is too long.");
      }

      let validation: ReturnType<typeof validateExternalUrl>;

      try {
        validation = validateExternalUrl(command.url);
      } catch {
        return deny("The destination URL could not be validated.");
      }

      if (!validation.valid) {
        return deny(
          validation.reason || "The destination URL is not permitted.",
        );
      }

      // External navigation always requires explicit confirmation.
      return allow(true);
    }

    case "chat_request": {
      if (command.url !== undefined) {
        return deny(
          "Chat commands cannot contain an external destination URL.",
        );
      }

      return allow(command.requiresConfirmation);
    }

    case "unsupported":
      return deny(
        "This command is not supported by the current browser action engine.",
      );

    default: {
      const exhaustiveCheck: never = command.kind;

      return deny(`Unknown command type: ${exhaustiveCheck}`);
    }
  }
}