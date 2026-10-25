
"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import type {
  CommandActionResult,
  CommandHistoryEntry,
  ParsedCommand,
} from "@/types/commandAction";

const MAX_HISTORY_ITEMS = 20;
const STORAGE_KEY = "orvyn-command-history-v1";

function isHistoryEntry(value: unknown): value is CommandHistoryEntry {
  if (!value || typeof value !== "object") {
    return false;
  }

  const item = value as Partial<CommandHistoryEntry>;

  return (
    typeof item.id === "string" &&
    typeof item.command === "string" &&
    typeof item.action === "string" &&
    typeof item.message === "string" &&
    typeof item.createdAt === "string" &&
    ["pending", "running", "success", "failed", "blocked"].includes(
      String(item.status),
    )
  );
}

function readStoredHistory(): CommandHistoryEntry[] {
  try {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);

    if (!stored) {
      return [];
    }

    const parsed: unknown = JSON.parse(stored);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter(isHistoryEntry)
      .slice(0, MAX_HISTORY_ITEMS);
  } catch {
    return [];
  }
}

export function useCommandHistory() {
  const [history, setHistory] = useState<CommandHistoryEntry[]>([]);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setHistory(readStoredHistory());
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    try {
      window.sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(history.slice(0, MAX_HISTORY_ITEMS)),
      );
    } catch {
      // History remains available in memory if storage is unavailable.
    }
  }, [history, isHydrated]);

  const recordCommand = useCallback(
    (
      command: ParsedCommand,
      result: CommandActionResult,
    ) => {
      const entry: CommandHistoryEntry = {
        id: command.id,
        command: command.originalText,
        action: command.title,
        status: result.status,
        message: result.message,
        createdAt: result.completedAt,
      };

      setHistory((current) =>
        [
          entry,
          ...current.filter((item) => item.id !== entry.id),
        ].slice(0, MAX_HISTORY_ITEMS),
      );
    },
    [],
  );

  const clearHistory = useCallback(() => {
    setHistory([]);

    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // The in-memory history is still cleared.
    }
  }, []);

  return {
    history,
    recordCommand,
    clearHistory,
  };
}
