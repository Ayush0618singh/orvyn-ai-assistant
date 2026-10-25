
export type CommandTelemetryEventType =
  | "command_prepared"
  | "command_started"
  | "command_succeeded"
  | "command_failed"
  | "command_blocked"
  | "confirmation_requested"
  | "confirmation_approved"
  | "confirmation_cancelled";

export interface CommandTelemetryEvent {
  id: string;
  commandId: string;
  type: CommandTelemetryEventType;
  commandKind: string;
  timestamp: string;
  durationMs?: number;
  message?: string;
}

const STORAGE_KEY = "orvyn-command-telemetry-v1";
const MAX_EVENTS = 200;

function isTelemetryEvent(value: unknown): value is CommandTelemetryEvent {
  if (!value || typeof value !== "object") return false;

  const event = value as Partial<CommandTelemetryEvent>;

  return (
    typeof event.id === "string" &&
    typeof event.commandId === "string" &&
    typeof event.type === "string" &&
    typeof event.commandKind === "string" &&
    typeof event.timestamp === "string"
  );
}

function createId(): string {
  if (
    typeof globalThis.crypto !== "undefined" &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return globalThis.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function recordCommandTelemetry(
  event: Omit<CommandTelemetryEvent, "id" | "timestamp">,
): void {
  if (typeof window === "undefined") return;

  try {
    const existing = readCommandTelemetry();

    const nextEvent: CommandTelemetryEvent = {
      ...event,
      id: createId(),
      timestamp: new Date().toISOString(),
    };

    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([...existing, nextEvent].slice(-MAX_EVENTS)),
    );
  } catch {
    // Telemetry must never break command execution.
  }
}

export function readCommandTelemetry(): CommandTelemetryEvent[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isTelemetryEvent).slice(-MAX_EVENTS);
  } catch {
    return [];
  }
}

export function clearCommandTelemetry(): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore unavailable storage.
  }
}
