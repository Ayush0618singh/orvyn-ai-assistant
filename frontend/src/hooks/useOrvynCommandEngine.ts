
"use client";

import { useCallback, useState } from "react";

import { useCommandHistory } from "@/hooks/useCommandHistory";
import { parseCommand } from "@/services/commandParser";
import { executeBrowserAction } from "@/services/browserActionService";

import type {
  CommandActionResult,
  ParsedCommand,
} from "@/types/commandAction";

interface CommandEngineState {
  command: string;
  pendingCommand: ParsedCommand | null;
  result: CommandActionResult | null;
  isExecuting: boolean;
}

function makeResult(
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

export function useOrvynCommandEngine() {
  const [state, setState] = useState<CommandEngineState>({
    command: "",
    pendingCommand: null,
    result: null,
    isExecuting: false,
  });

  const {
    history,
    recordCommand,
    clearHistory,
  } = useCommandHistory();

  const setCommand = useCallback((command: string) => {
    setState((current) => ({
      ...current,
      command,
      pendingCommand: null,
      result: null,
    }));
  }, []);

  const prepareCommand = useCallback(() => {
    const parsed = parseCommand(state.command);

    setState((current) => ({
      ...current,
      pendingCommand: parsed,
      result: null,
    }));

    return parsed;
  }, [state.command]);

  const executeCommand = useCallback(async () => {
    if (state.isExecuting) {
      return null;
    }

    const parsed =
      state.pendingCommand ?? parseCommand(state.command);

    setState((current) => ({
      ...current,
      pendingCommand: parsed,
      isExecuting: true,
      result: null,
    }));

    let executionResult: CommandActionResult;

    try {
      if (
        parsed.kind === "youtube_search" ||
        parsed.kind === "web_search" ||
        parsed.kind === "open_url"
      ) {
        executionResult = await executeBrowserAction(parsed);
      } else {
        executionResult = makeResult(
          parsed,
          "blocked",
          parsed.kind === "chat_request"
            ? "Open Chat Workspace to send this request to the connected AI chat service."
            : "No action was performed because this command has no supported integration yet.",
        );
      }
    } catch {
      executionResult = makeResult(
        parsed,
        "failed",
        "The action could not be completed. Check browser permissions and try again.",
      );
    }

    recordCommand(parsed, executionResult);

    setState((current) => ({
      ...current,
      result: executionResult,
      isExecuting: false,
    }));

    return executionResult;
  }, [
    state.command,
    state.isExecuting,
    state.pendingCommand,
    recordCommand,
  ]);

  const resetResult = useCallback(() => {
    setState((current) => ({
      ...current,
      result: null,
    }));
  }, []);

  return {
    command: state.command,
    setCommand,
    pendingCommand: state.pendingCommand,
    result: state.result,
    isExecuting: state.isExecuting,
    prepareCommand,
    executeCommand,
    resetResult,
    history,
    clearHistory,
  };
}
