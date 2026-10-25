
"use client";

const capabilities = [
  {
    name: "YouTube search",
    status: "Available",
    detail: "Opens a YouTube search for the supplied query.",
    state: "available",
  },
  {
    name: "Web search",
    status: "Available",
    detail: "Opens a browser search for the supplied query.",
    state: "available",
  },
  {
    name: "Open external URL",
    status: "Confirmation required",
    detail: "External navigation should be reviewed before execution.",
    state: "review",
  },
  {
    name: "Chat workspace",
    status: "UI integration",
    detail: "Opens the chat workspace; it does not guarantee automatic message submission.",
    state: "review",
  },
  {
    name: "Persistent memory",
    status: "Separate module",
    detail: "Use the existing Memories feature; command telemetry is not AI memory.",
    state: "separate",
  },
  {
    name: "External tools and agents",
    status: "Not verified here",
    detail: "Requires connected tool handlers, permissions and real execution tests.",
    state: "unverified",
  },
] as const;

const stateStyles = {
  available: "border-emerald-400/30 text-emerald-200 bg-emerald-400/5",
  review: "border-amber-400/30 text-amber-200 bg-amber-400/5",
  separate: "border-sky-400/30 text-sky-200 bg-sky-400/5",
  unverified: "border-slate-500/40 text-slate-300 bg-slate-400/5",
} as const;

export default function CommandCapabilityMatrix() {
  return (
    <section className="rounded-2xl border border-cyan-400/20 bg-slate-950/80 p-5 text-slate-100">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
        System capabilities
      </p>
      <h2 className="mt-2 text-xl font-semibold">Command capability matrix</h2>
      <p className="mt-1 text-sm text-slate-400">
        Current dashboard scope. Status labels describe this command workspace,
        not every ORVYN module.
      </p>

      <div className="mt-5 space-y-3">
        {capabilities.map((capability) => (
          <article
            key={capability.name}
            className="rounded-xl border border-white/10 bg-white/[0.025] p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-medium">{capability.name}</h3>
              <span
                className={`rounded-full border px-2.5 py-1 text-xs ${stateStyles[capability.state]}`}
              >
                {capability.status}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {capability.detail}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
