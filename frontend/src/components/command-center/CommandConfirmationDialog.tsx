
"use client";

interface CommandConfirmationDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}

export default function CommandConfirmationDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm action",
  onConfirm,
  onCancel,
  busy = false,
}: CommandConfirmationDialogProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) {
          onCancel();
        }
      }}
    >
      <section
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="orvyn-confirm-title"
        aria-describedby="orvyn-confirm-description"
        className="w-full max-w-md rounded-2xl border border-cyan-400/20 bg-slate-950 p-6 shadow-2xl shadow-cyan-950/30"
      >
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-amber-400/20 bg-amber-400/10 text-xl text-amber-300">
          !
        </div>

        <h2
          id="orvyn-confirm-title"
          className="text-lg font-semibold text-white"
        >
          {title}
        </h2>

        <p
          id="orvyn-confirm-description"
          className="mt-2 break-words text-sm leading-6 text-slate-400"
        >
          {description}
        </p>

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 transition hover:bg-white/5 disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-200 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Processing..." : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
