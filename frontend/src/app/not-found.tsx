
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <section className="w-full max-w-lg rounded-2xl border border-cyan-400/15 bg-slate-950/80 p-8 text-center shadow-2xl">
        <p className="text-sm font-semibold tracking-[0.25em] text-cyan-300">
          ORVYN / 404
        </p>

        <h1 className="mt-5 text-6xl font-bold tracking-tight text-white">
          404
        </h1>

        <h2 className="mt-4 text-xl font-semibold text-slate-100">
          Destination not found
        </h2>

        <p className="mt-3 text-sm leading-7 text-slate-400">
          This page does not exist or may have moved.
          Return to ORVYN and continue from your workspace.
        </p>

        <Link
          href="/"
          className="mt-7 inline-flex min-h-11 items-center justify-center rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-5 py-3 font-semibold text-cyan-200 transition hover:bg-cyan-400/20"
        >
          Return to ORVYN
        </Link>
      </section>
    </main>
  );
}
