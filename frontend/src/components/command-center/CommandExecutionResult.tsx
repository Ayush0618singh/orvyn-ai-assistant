
import type { CommandActionResult } from "@/types/commandAction";
import CommandStatusBadge from "@/components/command-center/CommandStatusBadge";

interface CommandExecutionResultProps {
  result: CommandActionResult | null;
}

export default function CommandExecutionResult({
  result,
}: CommandExecutionResultProps) {
  if (!result) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <p className="text-sm text-slate-400">
          Your command result will appear here after execution.
        </p>
      </div>
    );
  }

  const isFailure =
    result.status === "failed" || result.status === "blocked";

  return (
    <section
      aria-live="polite"
      aria-label="Command execution result"
      className="rounded-xl border border-white/10 bg-slate-950/50 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">
          Execution result
        </h3>

        <CommandStatusBadge status={result.status} />
      </div>

      <p
        className={[
          "mt-3 break-words text-sm leading-6",
          isFailure ? "text-amber-200" : "text-slate-300",
        ].join(" ")}
      >
        {result.message}
      </p>

      <p className="mt-3 text-xs text-slate-500">
        Completed at{" "}
        {Number.isNaN(Date.parse(result.completedAt))
          ? "Unknown time"
          : new Date(result.completedAt).toLocaleString()}
      </p>
    </section>
  );
}
