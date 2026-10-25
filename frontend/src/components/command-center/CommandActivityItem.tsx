
"use client";

import type { CommandHistoryEntry } from "@/types/commandAction";
import CommandStatusBadge from "@/components/command-center/CommandStatusBadge";

interface CommandActivityItemProps {
  entry: CommandHistoryEntry;
}

export default function CommandActivityItem({
  entry,
}: CommandActivityItemProps) {
  const timestamp = Date.parse(entry.createdAt);

  return (
    <article className="relative rounded-xl border border-white/10 bg-white/[0.02] p-4 transition hover:border-cyan-400/20 hover:bg-white/[0.035]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="break-words text-sm font-medium text-slate-100">
            {entry.action}
          </h4>

          <p className="mt-1 break-words text-xs leading-5 text-slate-500">
            {entry.command}
          </p>
        </div>

        <CommandStatusBadge status={entry.status} />
      </div>

      <p className="mt-3 break-words text-sm leading-6 text-slate-400">
        {entry.message}
      </p>

      <p className="mt-3 text-xs text-slate-600">
        {Number.isNaN(timestamp)
          ? "Time unavailable"
          : new Date(timestamp).toLocaleString()}
      </p>
    </article>
  );
}
