
export default function Loading() {
  return (
    <main
      role="status"
      aria-live="polite"
      className="flex min-h-screen items-center justify-center px-6"
    >
      <div className="flex w-full max-w-sm flex-col items-center rounded-2xl border border-cyan-400/15 bg-slate-950/80 p-8 text-center shadow-2xl shadow-cyan-950/20">
        <div className="relative mb-6 grid size-20 place-items-center rounded-full border border-cyan-300/40 bg-cyan-400/5">
          <div className="absolute inset-2 animate-spin rounded-full border-2 border-transparent border-t-cyan-300" />
          <span className="text-xl font-bold tracking-[0.2em] text-cyan-200">
            O
          </span>
        </div>

        <p className="text-lg font-semibold tracking-[0.18em] text-white">
          ORVYN
        </p>

        <p className="mt-2 text-sm text-slate-400">
          Preparing your workspace…
        </p>

        <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-slate-800">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-cyan-300" />
        </div>
      </div>
    </main>
  );
}
