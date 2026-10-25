
"use client";

import type { CommandHistoryEntry } from "@/types/commandAction";
import CommandActivityItem from "@/components/command-center/CommandActivityItem";

interface CommandActivityFeedProps {
  entries: CommandHistoryEntry[];
  onClear?: () => void;
  limit?: number;
}

export default function CommandActivityFeed({
  entries,
  onClear,
  limit = 5,
}: CommandActivityFeedProps) {
  const safeLimit = Math.max(1, Math.min(limit, 20));
  const recentEntries = entries.slice(0, safeLimit);

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-300/70">
            Agent activity
          </p>
          <h3 className="mt-1 text-lg font-semibold text-white">
            Recent commands
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            {entries.length} recorded {entries.length === 1 ? "action" : "actions"}
          </p>
        </div>

        {onClear && entries.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400 transition hover:border-rose-400/30 hover:text-rose-300"
          >
            Clear history
          </button>
        )}
      </header>

      {recentEntries.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center">
          <p className="text-sm text-slate-300">
            No command activity yet.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Your recent actions will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {recentEntries.map((entry) => (
            <CommandActivityItem key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </section>
  );
}
