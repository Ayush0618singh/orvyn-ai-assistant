
"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log only non-sensitive diagnostic information.
    console.error("ORVYN route error:", {
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <section
        role="alert"
        className="w-full max-w-lg rounded-2xl border border-rose-400/20 bg-slate-950/90 p-8 shadow-2xl"
      >
        <div className="mb-5 grid size-12 place-items-center rounded-xl border border-rose-400/25 bg-rose-400/10 text-xl text-rose-300">
          !
        </div>

        <p className="text-xs font-semibold tracking-[0.2em] text-cyan-300">
          ORVYN / ERROR RECOVERY
        </p>

        <h1 className="mt-3 text-2xl font-semibold text-white">
          Something went wrong
        </h1>

        <p className="mt-3 text-sm leading-7 text-slate-400">
          This page encountered an unexpected error.
          You can retry the operation or return to the
          main workspace.
        </p>

        {error.digest && (
          <p className="mt-4 break-all text-xs text-slate-500">
            Reference: {error.digest}
          </p>
        )}

        <div className="mt-7 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-400/20"
          >
            Try again
          </button>

          <a
            href="/"
            className="rounded-lg border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
          >
            Return to ORVYN
          </a>
        </div>
      </section>
    </main>
  );
}
