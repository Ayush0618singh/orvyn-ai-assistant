
"use client";

import CommandTelemetryPanel from "@/components/command-center/CommandTelemetryPanel";
import CommandCapabilityMatrix from "@/components/command-center/CommandCapabilityMatrix";

export default function CommandInsightsSection() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
          ORVYN intelligence layer
        </p>
        <h2 className="mt-2 text-2xl font-semibold text-white">
          Execution insights
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Review supported command capabilities and inspect the activity
          recorded during this browser session.
        </p>
      </div>

      <CommandTelemetryPanel />
      <CommandCapabilityMatrix />
    </section>
  );
}
