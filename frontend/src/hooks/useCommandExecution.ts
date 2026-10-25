
"use client";

import { useCallback, useRef, useState } from "react";

import type {
  CommandActionResult,
  ParsedCommand,
} from "@/types/commandAction";

import { coordinateCommandExecution } from "@/services/commandExecutionCoordinator";

interface UseCommandExecutionReturn {
  result: CommandActionResult | null;
  isExecuting: boolean;
  pendingConfirmation: ParsedCommand | null;
  prepareCommand: (command: ParsedCommand) => Promise<CommandActionResult | null>;
  confirmCommand: () => Promise<CommandActionResult | null>;
  cancelConfirmation: () => void;
  resetExecution: () => void;
}

export function useCommandExecution(): UseCommandExecutionReturn {
  const [result, setResult] = useState<CommandActionResult | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] =
    useState<ParsedCommand | null>(null);

  const executionLock = useRef(false);
  const pendingRef = useRef<ParsedCommand | null>(null);

  const runCommand = useCallback(
    async (
      command: ParsedCommand,
      confirmed: boolean,
    ): Promise<CommandActionResult | null> => {
      if (executionLock.current) {
        return null;
      }

      executionLock.current = true;
      setIsExecuting(true);
      setResult(null);

      try {
        const executionResult = await coordinateCommandExecution(
          command,
          { confirmed },
        );

        if (executionResult.status === "pending") {
          pendingRef.current = command;
          setPendingConfirmation(command);
          setResult(executionResult);
          return executionResult;
        }

        pendingRef.current = null;
        setPendingConfirmation(null);
        setResult(executionResult);

        return executionResult;
      } catch {
        const failure: CommandActionResult = {
          commandId: command.id,
          status: "failed",
          message: "ORVYN could not complete this action. Please try again.",
          completedAt: new Date().toISOString(),
        };

        setResult(failure);
        return failure;
      } finally {
        executionLock.current = false;
        setIsExecuting(false);
      }
    },
    [],
  );

  const prepareCommand = useCallback(
    async (command: ParsedCommand) => {
      pendingRef.current = null;
      setPendingConfirmation(null);
      return runCommand(command, false);
    },
    [runCommand],
  );

  const confirmCommand = useCallback(async () => {
    const command = pendingRef.current;

    if (!command) {
      return null;
    }

    pendingRef.current = null;
    setPendingConfirmation(null);

    return runCommand(command, true);
  }, [runCommand]);

  const cancelConfirmation = useCallback(() => {
    const command = pendingRef.current;

    pendingRef.current = null;
    setPendingConfirmation(null);

    if (command) {
      setResult({
        commandId: command.id,
        status: "blocked",
        message: "Action cancelled by the user.",
        completedAt: new Date().toISOString(),
      });
    }
  }, []);

  const resetExecution = useCallback(() => {
    if (executionLock.current) {
      return;
    }

    pendingRef.current = null;
    setPendingConfirmation(null);
    setResult(null);
  }, []);

  return {
    result,
    isExecuting,
    pendingConfirmation,
    prepareCommand,
    confirmCommand,
    cancelConfirmation,
    resetExecution,
  };
}

export default useCommandExecution;
