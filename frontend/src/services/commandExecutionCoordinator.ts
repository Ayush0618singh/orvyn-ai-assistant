
import type {
  CommandActionResult,
  ParsedCommand,
} from "@/types/commandAction";

import { evaluateCommandPolicy } from "@/services/commandPolicy";
import { executeBrowserAction } from "@/services/browserActionService";
import { recordCommandTelemetry } from "@/services/commandTelemetry";

export interface CoordinateExecutionOptions {
  confirmed?: boolean;
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

function recordTelemetry(
  command: ParsedCommand,
  type:
    | "command_started"
    | "command_succeeded"
    | "command_failed"
    | "command_blocked"
    | "confirmation_requested"
    | "confirmation_approved",
  message?: string,
  durationMs?: number,
): void {
  recordCommandTelemetry({
    commandId: command.id,
    commandKind: command.kind,
    type,
    message,
    durationMs,
  });
}

export async function coordinateCommandExecution(
  command: ParsedCommand,
  options: CoordinateExecutionOptions = {},
): Promise<CommandActionResult> {
  let policy: ReturnType<typeof evaluateCommandPolicy>;

  try {
    policy = evaluateCommandPolicy(command);
  } catch {
    const result = makeResult(
      command,
      "blocked",
      "The command could not pass the security policy check.",
    );

    recordTelemetry(command, "command_blocked", result.message);
    return result;
  }

  if (!policy.allowed) {
    const result = makeResult(
      command,
      "blocked",
      policy.reason || "This action is not permitted.",
    );

    recordTelemetry(command, "command_blocked", result.message);
    return result;
  }

  const requiresConfirmation =
    command.requiresConfirmation || policy.requiresConfirmation;

  if (requiresConfirmation && options.confirmed !== true) {
    const result = makeResult(
      command,
      "pending",
      "Review this external action and confirm before execution.",
    );

    recordTelemetry(
      command,
      "confirmation_requested",
      result.message,
    );

    return result;
  }

  if (requiresConfirmation) {
    recordTelemetry(
      command,
      "confirmation_approved",
      "User approved the external action.",
    );
  }

  const startedAt = Date.now();

  recordTelemetry(command, "command_started");

  try {
    const result = await executeBrowserAction(command);
    const durationMs = Date.now() - startedAt;

    if (result.status === "success") {
      recordTelemetry(
        command,
        "command_succeeded",
        result.message,
        durationMs,
      );
    } else if (result.status === "blocked") {
      recordTelemetry(
        command,
        "command_blocked",
        result.message,
        durationMs,
      );
    } else if (result.status === "failed") {
      recordTelemetry(
        command,
        "command_failed",
        result.message,
        durationMs,
      );
    }

    return result;
  } catch {
    const result = makeResult(
      command,
      "failed",
      "Execution failed unexpectedly. Check the action and try again.",
    );

    recordTelemetry(
      command,
      "command_failed",
      result.message,
      Date.now() - startedAt,
    );

    return result;
  }
}
