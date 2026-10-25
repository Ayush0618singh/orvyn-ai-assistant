import type {
  CommandActionResult,
  ParsedCommand,
} from "@/types/commandAction";

import {
  buildSearchUrl,
  validateExternalUrl,
} from "@/utils/commandSecurity";

const MAX_QUERY_LENGTH = 500;
const MAX_URL_LENGTH = 2048;

function createResult(
  command: ParsedCommand,
  status: CommandActionResult["status"],
  message: string,
): CommandActionResult {
  return {
    commandId: command.id,
    status,
    message,
    completedAt: new Date().toISOString(),
  };
}

function isValidQuery(
  query: string | undefined,
): query is string {
  return (
    typeof query === "string" &&
    query.trim().length > 0 &&
    query.trim().length <= MAX_QUERY_LENGTH
  );
}

function openExternalUrl(url: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    const openedWindow = window.open(
      url,
      "_blank",
      "noopener,noreferrer",
    );

    // Browsers may return null when noopener is enabled.
    // A null result does not reliably indicate whether a tab opened.
    return openedWindow !== null;
  } catch {
    return false;
  }
}

function executeSearch(
  command: ParsedCommand,
  provider: "youtube" | "google" | "google_images",
): CommandActionResult {
  const query = command.query?.trim();

  if (!isValidQuery(query)) {
    return createResult(
      command,
      "failed",
      "Enter a valid search query of up to 500 characters.",
    );
  }

  let targetUrl: string;

  try {
    targetUrl = buildSearchUrl(provider, query);
  } catch {
    return createResult(
      command,
      "failed",
      "Could not construct a valid search URL.",
    );
  }

  const validation = validateExternalUrl(targetUrl);

  if (!validation.valid) {
    return createResult(
      command,
      "blocked",
      validation.reason || "The search destination was blocked by security policy.",
    );
  }

  const opened = openExternalUrl(validation.normalizedUrl);

  if (!opened) {
    return createResult(
      command,
      "failed",
      "The browser may have blocked the new tab. Allow pop-ups or use the in-app search workspace.",
    );
  }

  const providerName =
    provider === "youtube"
      ? "YouTube"
      : provider === "google_images"
        ? "Google Images"
        : "Google";

  const actionDescription =
    provider === "youtube"
      ? "Select a result to play it. ORVYN has not verified playback."
      : "The search results have been requested in a new tab.";

  return createResult(
    command,
    "success",
    `${providerName} search opened for "${query}". ${actionDescription}`,
  );
}

export async function executeBrowserAction(
  command: ParsedCommand,
): Promise<CommandActionResult> {
  if (typeof window === "undefined") {
    return createResult(
      command,
      "failed",
      "Browser actions are only available in the browser.",
    );
  }

  if (!command || typeof command !== "object") {
    return {
      commandId: "unknown",
      status: "blocked",
      message: "Invalid command.",
      completedAt: new Date().toISOString(),
    };
  }

  try {
    switch (command.kind) {
      case "youtube_search":
        return executeSearch(command, "youtube");

      case "web_search":
        return executeSearch(command, "google");

      case "google_images":
        return executeSearch(command, "google_images");

      case "open_url": {
        const rawUrl = command.url?.trim();

        if (!rawUrl) {
          return createResult(
            command,
            "failed",
            "No destination URL was provided.",
          );
        }

        if (rawUrl.length > MAX_URL_LENGTH) {
          return createResult(
            command,
            "blocked",
            "The destination URL is too long.",
          );
        }

        const validation = validateExternalUrl(rawUrl);

        if (!validation.valid) {
          return createResult(
            command,
            "blocked",
            validation.reason || "The destination URL is not permitted.",
          );
        }

        if (!command.requiresConfirmation) {
          return createResult(
            command,
            "blocked",
            "This external navigation requires explicit user confirmation.",
          );
        }

        if (!openExternalUrl(validation.normalizedUrl)) {
          return createResult(
            command,
            "failed",
            "The browser may have blocked the new tab. Allow pop-ups and try again.",
          );
        }

        return createResult(
          command,
          "success",
          `Opened the external destination: ${validation.url.hostname}.`,
        );
      }

      case "chat_request":
        return createResult(
          command,
          "blocked",
          "Chat requests must be handled by the connected Chat Workspace.",
        );

      case "unsupported":
        return createResult(
          command,
          "blocked",
          "This command does not have a supported browser action.",
        );

      default: {
        const exhaustiveCheck: never = command.kind;

        return createResult(
          command,
          "blocked",
          `Unsupported command type: ${exhaustiveCheck}`,
        );
      }
    }
  } catch (error: unknown) {
    const message =
      error instanceof Error
        ? error.message
        : "Unknown browser action error.";

    console.error("[ORVYN Browser Action]", message);

    return createResult(
      command,
      "failed",
      "The browser action failed. Check the destination and try again.",
    );
  }
}

export function validateHttpUrl(rawUrl: string): boolean {
  try {
    return validateExternalUrl(rawUrl).valid;
  } catch {
    return false;
  }
}