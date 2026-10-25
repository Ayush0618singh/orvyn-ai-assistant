
"use client";

import type {
  CommandHistoryEntry,
} from "@/types/commandAction";

interface CommandHistoryPanelProps {
  history: CommandHistoryEntry[];
  onClear?: () => void;
}

function statusLabel(status: CommandHistoryEntry["status"]) {
  switch (status) {
    case "success":
      return "Completed";
    case "running":
      return "Running";
    case "failed":
      return "Failed";
    case "blocked":
      return "Blocked";
    default:
      return "Pending";
  }
}

export default function CommandHistoryPanel({
  history,
  onClear,
}: CommandHistoryPanelProps) {
  return (
    <section className="rounded-2xl border border-cyan-900/60 bg-slate-950/70 p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold tracking-[0.18em] text-cyan-400">
            ACTION MONITOR
          </p>
          <h3 className="mt-1 text-base font-semibold text-slate-100">
            Recent commands
          </h3>
        </div>

        {onClear && history.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-cyan-700 hover:text-cyan-200"
          >
            Clear
          </button>
        )}
      </div>

      {history.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 px-4 py-8 text-center">
          <p className="text-sm text-slate-300">
            No commands executed yet
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Your recent browser actions will appear here.
          </p>
        </div>
      ) : (
        <ol className="space-y-2">
          {history.map((item) => (
            <li
              key={item.id}
              className="rounded-xl border border-slate-800 bg-slate-900/70 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium text-slate-100">
                    {item.action}
                  </p>
                  <p className="mt-1 break-words text-xs text-slate-400">
                    {item.command}
                  </p>
                </div>

                <span
                  className={`shrink-0 rounded-full border px-2 py-1 text-[10px] ${
                    item.status === "success"
                      ? "border-emerald-800 bg-emerald-950/60 text-emerald-300"
                      : item.status === "failed" ||
                          item.status === "blocked"
                        ? "border-amber-800 bg-amber-950/50 text-amber-300"
                        : "border-cyan-900 bg-cyan-950/50 text-cyan-300"
                  }`}
                >
                  {statusLabel(item.status)}
                </span>
              </div>

              <p className="mt-2 break-words text-xs leading-5 text-slate-400">
                {item.message}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
