
import type { CommandHistoryEntry } from "@/types/commandAction";

const STORAGE_KEY = "orvyn-command-history-v1";
const MAX_ENTRIES = 20;

function isHistoryEntry(value: unknown): value is CommandHistoryEntry {
  if (!value || typeof value !== "object") {
    return false;
  }

  const entry = value as Partial<CommandHistoryEntry>;

  const validStatuses = [
    "pending",
    "running",
    "success",
    "failed",
    "blocked",
  ];

  return (
    typeof entry.id === "string" &&
    typeof entry.command === "string" &&
    typeof entry.action === "string" &&
    typeof entry.message === "string" &&
    typeof entry.createdAt === "string" &&
    typeof entry.status === "string" &&
    validStatuses.includes(entry.status)
  );
}

export function readCommandHistory(): CommandHistoryEntry[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return [];
    }

    const parsed: unknown = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter(isHistoryEntry)
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

export function writeCommandHistory(
  entries: CommandHistoryEntry[],
): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(entries.filter(isHistoryEntry).slice(0, MAX_ENTRIES)),
    );

    return true;
  } catch {
    return false;
  }
}

export function clearCommandHistoryStorage(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}
