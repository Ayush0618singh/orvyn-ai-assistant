
"use client";

import type { ParsedCommand } from "@/types/commandAction";

interface CommandPreviewCardProps {
  command: ParsedCommand | null;
  onExecute: () => void;
  onEdit?: () => void;
  busy?: boolean;
}

export default function CommandPreviewCard({
  command,
  onExecute,
  onEdit,
  busy = false,
}: CommandPreviewCardProps) {
  if (!command) {
    return (
      <section className="rounded-2xl border border-white/10 bg-slate-950/40 p-5">
        <p className="text-sm font-medium text-slate-200">
          Command preview
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Enter a command or use your microphone to prepare an action.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-cyan-400/20 bg-slate-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-300/70">
            Prepared action
          </p>
          <h3 className="mt-2 text-lg font-semibold text-white">
            {command.title}
          </h3>
        </div>

        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
          {command.kind.replaceAll("_", " ")}
        </span>
      </div>

      <p className="mt-3 break-words text-sm leading-6 text-slate-400">
        {command.description}
      </p>

      <div className="mt-4 rounded-xl border border-white/5 bg-black/20 p-3">
        <p className="text-xs text-slate-500">Original command</p>
        <p className="mt-1 break-words text-sm text-slate-200">
          {command.originalText}
        </p>
      </div>

      {command.requiresConfirmation && (
        <p className="mt-3 text-xs leading-5 text-amber-300">
          Confirmation is required before this action can proceed.
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        {onEdit && (
          <button
            type="button"
            disabled={busy}
            onClick={onEdit}
            className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-50"
          >
            Edit command
          </button>
        )}

        <button
          type="button"
          disabled={busy}
          onClick={onExecute}
          className="rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-200 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Executing..." : "Execute action"}
        </button>
      </div>
    </section>
  );
}
