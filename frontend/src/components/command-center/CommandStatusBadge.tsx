
import type { CommandActionStatus } from "@/types/commandAction";

interface CommandStatusBadgeProps {
  status: CommandActionStatus;
  className?: string;
}

const STATUS_LABELS: Record<CommandActionStatus, string> = {
  pending: "Pending",
  running: "Running",
  success: "Completed",
  failed: "Failed",
  blocked: "Blocked",
};

const STATUS_STYLES: Record<CommandActionStatus, string> = {
  pending:
    "border-slate-500/30 bg-slate-500/10 text-slate-300",
  running:
    "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
  success:
    "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  failed:
    "border-rose-400/30 bg-rose-400/10 text-rose-300",
  blocked:
    "border-amber-400/30 bg-amber-400/10 text-amber-300",
};

export default function CommandStatusBadge({
  status,
  className = "",
}: CommandStatusBadgeProps) {
  return (
    <span
      role="status"
      className={[
        "inline-flex items-center gap-2 rounded-full border px-3 py-1",
        "text-xs font-medium tracking-wide",
        STATUS_STYLES[status],
        className,
      ].join(" ")}
    >
      <span
        aria-hidden="true"
        className={[
          "h-1.5 w-1.5 rounded-full",
          status === "running"
            ? "animate-pulse bg-current"
            : "bg-current",
        ].join(" ")}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
