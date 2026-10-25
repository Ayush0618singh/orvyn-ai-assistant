
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  clearCommandTelemetry,
  readCommandTelemetry,
  type CommandTelemetryEvent,
} from "@/services/commandTelemetry";

export default function CommandTelemetryPanel() {
  const [events, setEvents] = useState<CommandTelemetryEvent[]>([]);

  const refresh = useCallback(() => {
    setEvents(readCommandTelemetry());
  }, []);

  useEffect(() => {
    refresh();

    const handleStorage = () => refresh();
    window.addEventListener("storage", handleStorage);

    return () => window.removeEventListener("storage", handleStorage);
  }, [refresh]);

  const metrics = useMemo(() => {
    const completed = events.filter((event) =>
      [
        "command_succeeded",
        "command_failed",
        "command_blocked",
      ].includes(event.type),
    );

    const successful = completed.filter(
      (event) => event.type === "command_succeeded",
    ).length;

    const durations = completed
      .map((event) => event.durationMs)
      .filter((value): value is number => typeof value === "number");

    return {
      total: completed.length,
      successful,
      blocked: completed.filter((event) => event.type === "command_blocked")
        .length,
      failed: completed.filter((event) => event.type === "command_failed")
        .length,
      successRate:
        completed.length > 0
          ? Math.round((successful / completed.length) * 100)
          : 0,
      averageDuration:
        durations.length > 0
          ? Math.round(
              durations.reduce((total, value) => total + value, 0) /
                durations.length,
            )
          : null,
    };
  }, [events]);

  function clearEvents() {
    clearCommandTelemetry();
    refresh();
  }

  const statCards = [
    { label: "Completed outcomes", value: metrics.total },
    { label: "Successful", value: metrics.successful },
    { label: "Blocked", value: metrics.blocked },
    { label: "Failed", value: metrics.failed },
  ];

  return (
    <section className="rounded-2xl border border-cyan-400/20 bg-slate-950/80 p-5 text-slate-100 shadow-xl shadow-cyan-950/10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            ORVYN · Observability
          </p>
          <h2 className="mt-2 text-xl font-semibold">Command telemetry</h2>
          <p className="mt-1 text-sm text-slate-400">
            Session-level execution metrics. Not server-side analytics.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={refresh}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm hover:border-cyan-400/60"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={clearEvents}
            className="rounded-lg border border-rose-400/30 px-3 py-2 text-sm text-rose-200 hover:bg-rose-400/10"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {statCards.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-white/10 bg-white/[0.03] p-4"
          >
            <p className="text-xs text-slate-400">{stat.label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-white/10 p-4">
          <p className="text-sm text-slate-400">Success rate</p>
          <p className="mt-1 text-xl font-semibold">{metrics.successRate}%</p>
          <div
            className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
            aria-label="Command success rate"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={metrics.successRate}
          >
            <div
              className="h-full rounded-full bg-cyan-400 transition-all"
              style={{ width: `${metrics.successRate}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-white/10 p-4">
          <p className="text-sm text-slate-400">Average recorded duration</p>
          <p className="mt-1 text-xl font-semibold">
            {metrics.averageDuration === null
              ? "—"
              : `${metrics.averageDuration} ms`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Calculated only from outcomes that include timing data.
          </p>
        </div>
      </div>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-200">Recent events</h3>

        {events.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-slate-700 p-4 text-sm text-slate-400">
            No telemetry events yet. Execute a command to populate this panel.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {[...events].reverse().slice(0, 8).map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3"
              >
                <div className="min-w-0">
                  <p className="break-words text-sm text-slate-200">
                    {event.type.replaceAll("_", " ")}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {event.commandKind} ·{" "}
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </p>
                  {event.message && (
                    <p className="mt-1 break-words text-xs text-slate-400">
                      {event.message}
                    </p>
                  )}
                </div>

                {typeof event.durationMs === "number" && (
                  <span className="text-xs tabular-nums text-cyan-200">
                    {event.durationMs} ms
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
