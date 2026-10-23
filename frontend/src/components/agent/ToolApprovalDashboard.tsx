
"use client";

import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";

import Link from "next/link";

import { useAuth } from "@/contexts/AuthContext";

import {
  approveToolApproval,
  denyToolApproval,
  executeToolApproval,
  listToolApprovals,
  requestWorkspaceFileApproval,
} from "@/services/toolApprovalService";

import type {
  ApprovalFilter,
  ToolApproval,
  ToolExecutionResponse,
} from "@/types/toolApproval";

const FILTERS: ApprovalFilter[] = [
  "all",
  "pending",
  "approved",
  "denied",
  "consumed",
  "expired",
];

function formatDate(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

export default function ToolApprovalDashboard() {
  const { user, loading: authLoading } =
    useAuth();

  const [items, setItems] =
    useState<ToolApproval[]>([]);

  const [filter, setFilter] =
    useState<ApprovalFilter>("all");

  const [loading, setLoading] =
    useState(false);

  const [busyId, setBusyId] =
    useState<string | null>(null);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [filename, setFilename] =
    useState("notes.txt");

  const [content, setContent] =
    useState("");

  const [total, setTotal] = useState(0);

  const [lastExecution, setLastExecution] =
    useState<ToolExecutionResponse | null>(null);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      if (!user) return;

      try {
        const result = await listToolApprovals({
          status: filter,
          limit: 50,
          offset: 0,
          signal,
        });

        if (signal?.aborted) return;

        setItems(result.items);
        setTotal(result.total);
      } catch (err) {
        if (signal?.aborted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Could not load approvals."
        );
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [filter, user]
  );

  useEffect(() => {
    if (!user) return;

    const controller = new AbortController();

    const timeout = window.setTimeout(() => {
      if (!controller.signal.aborted) {
        void refresh(controller.signal);
      }
    }, 0);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [refresh, user]);

  async function reload() {
    setLoading(true);
    await refresh();
  }

  async function createRequest(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setBusyId("create");
    setError("");
    setNotice("");

    try {
      const result =
        await requestWorkspaceFileApproval({
          filename,
          content,
        });

      setNotice(
        `Approval request created: ${result.id}`
      );

      setContent("");
      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Request failed."
      );
    } finally {
      setBusyId(null);
    }
  }

  async function performAction(
    approval: ToolApproval,
    action: "approve" | "deny" | "execute"
  ) {
    if (
      action === "execute" &&
      !window.confirm(
        `Execute "${approval.tool_name}"?`
      )
    ) {
      return;
    }

    setBusyId(approval.id);
    setError("");
    setNotice("");
    setLastExecution(null);

    try {
      if (action === "approve") {
        await approveToolApproval(approval.id);
        setNotice("Approval granted.");
      }

      if (action === "deny") {
        await denyToolApproval(approval.id);
        setNotice("Request denied.");
      }

      if (action === "execute") {
        const result =
          await executeToolApproval(approval.id);

        setLastExecution(result);

        setNotice(
          `Execution status: ${result.status}`
        );
      }

      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Action failed."
      );
    } finally {
      setBusyId(null);
    }
  }

  if (authLoading) {
    return (
      <main className="p-8">
        Checking authentication...
      </main>
    );
  }

  if (!user) {
    return (
      <main className="p-8">
        <h1 className="text-2xl font-semibold">
          Tool Approvals
        </h1>

        <p className="mt-3">
          Please sign in to ORVYN.
        </p>

        <Link href="/" className="underline">
          Return to ORVYN
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 pb-16 md:p-8">
      <header>
        <Link
          href="/"
          className="text-sm underline"
        >
          ← Back to ORVYN
        </Link>

        <h1 className="mt-2 text-3xl font-semibold">
          Agent Tool Approvals
        </h1>

        <p className="mt-2 text-sm text-gray-500">
          Review and authorize agent actions.
          Authentication uses your existing
          ORVYN login.
        </p>
      </header>

      <section className="rounded-xl border p-5">
        <h2 className="text-lg font-semibold">
          Request a Workspace File
        </h2>

        <p className="mt-2 text-sm text-gray-500">
          Only new .txt files are supported.
          Existing files cannot be overwritten.
        </p>

        <form
          onSubmit={createRequest}
          className="mt-4 space-y-3"
        >
          <label className="block space-y-1 text-sm">
            <span>Filename</span>

            <input
              value={filename}
              onChange={(event) =>
                setFilename(event.target.value)
              }
              required
              maxLength={68}
              className="w-full rounded-lg border bg-transparent p-3"
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span>File Content</span>

            <textarea
              value={content}
              onChange={(event) =>
                setContent(event.target.value)
              }
              required
              maxLength={4096}
              rows={5}
              placeholder="Write your text..."
              className="w-full rounded-lg border bg-transparent p-3"
            />
          </label>

          <button
            type="submit"
            disabled={busyId !== null}
            className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
          >
            {busyId === "create"
              ? "Submitting..."
              : "Request File Creation"}
          </button>
        </form>
      </section>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-500 p-4 text-sm text-red-500"
        >
          {error}
        </div>
      )}

      {notice && (
        <div
          role="status"
          className="rounded-lg border p-4 text-sm"
        >
          {notice}
        </div>
      )}

      {lastExecution && (
        <section className="rounded-xl border p-5">
          <h2 className="font-semibold">
            Last Execution Result
          </h2>

          <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-xs">
            {JSON.stringify(
              lastExecution,
              null,
              2
            )}
          </pre>
        </section>
      )}

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">
              Approval Requests
            </h2>

            <p className="text-sm text-gray-500">
              {total} matching requests
            </p>
          </div>

          <button
            type="button"
            onClick={() => void reload()}
            disabled={loading}
            className="rounded-lg border px-4 py-2 text-sm"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>

        <select
          value={filter}
          onChange={(event) =>
            setFilter(
              event.target.value as ApprovalFilter
            )
          }
          aria-label="Filter approvals"
          className="rounded-lg border bg-transparent p-3 text-sm"
        >
          {FILTERS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>

        {loading && (
          <p className="text-sm text-gray-500">
            Loading approvals...
          </p>
        )}

        {!loading && items.length === 0 && (
          <p className="rounded-xl border p-5 text-sm text-gray-500">
            No approval requests found.
          </p>
        )}

        {items.map((approval) => (
          <article
            key={approval.id}
            className="space-y-3 rounded-xl border p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">
                {approval.tool_name}
              </h3>

              <span className="rounded-full border px-3 py-1 text-xs">
                {approval.status}
              </span>
            </div>

            <div className="space-y-1 text-xs text-gray-500">
              <p>
                Risk: {approval.risk_level}
              </p>

              <p>
                Created:{" "}
                {formatDate(approval.created_at)}
              </p>

              <p>
                Expires:{" "}
                {formatDate(approval.expires_at)}
              </p>

              <p className="break-all">
                ID: {approval.id}
              </p>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">
                Requested Arguments
              </p>

              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg border p-3 text-xs">
                {JSON.stringify(
                  approval.arguments,
                  null,
                  2
                )}
              </pre>
            </div>

            <div className="flex flex-wrap gap-2">
              {approval.status === "pending" && (
                <>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() =>
                      void performAction(
                        approval,
                        "approve"
                      )
                    }
                    className="rounded-lg bg-green-700 px-4 py-2 text-sm text-white disabled:opacity-50"
                  >
                    Approve
                  </button>

                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() =>
                      void performAction(
                        approval,
                        "deny"
                      )
                    }
                    className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50"
                  >
                    Deny
                  </button>
                </>
              )}

              {approval.status === "approved" && (
                <button
                  type="button"
                  disabled={busyId !== null}
                  onClick={() =>
                    void performAction(
                      approval,
                      "execute"
                    )
                  }
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  Execute Approved Action
                </button>
              )}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
