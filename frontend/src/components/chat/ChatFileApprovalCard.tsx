
"use client";

import Link from "next/link";
import { useState } from "react";

import {
  approveToolApproval,
  denyToolApproval,
  executeToolApproval,
  getToolApproval,
} from "@/services/toolApprovalService";

import type {
  ToolApproval,
  ToolExecutionResponse,
} from "@/types/toolApproval";

interface Props {
  initialApproval: ToolApproval;
}

/**
 * Backend timestamps are expected to represent UTC.
 *
 * Examples:
 * 2026-10-20T12:12:30
 * 2026-10-20T12:12:30Z
 * 2026-10-20T12:12:30+00:00
 *
 * Naive timestamps are interpreted as UTC.
 * Explicit timezone offsets are preserved.
 */
function parseBackendTimestamp(value: string): Date {
  const normalized = value.trim();

  const hasTimezone =
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized);

  return new Date(
    hasTimezone
      ? normalized
      : `${normalized}Z`
  );
}

function formatExpiry(value: string): string {
  const date = parseBackendTimestamp(value);

  if (Number.isNaN(date.getTime())) {
    return "Invalid expiry timestamp";
  }

  return date.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function isApprovalExpired(value: string): boolean {
  const expiry = parseBackendTimestamp(value).getTime();

  // Fail closed for invalid timestamps.
  if (!Number.isFinite(expiry)) {
    return true;
  }

  return expiry <= Date.now();
}

export default function ChatFileApprovalCard({
  initialApproval,
}: Props) {
  const [approval, setApproval] =
    useState<ToolApproval>(initialApproval);

  const [execution, setExecution] =
    useState<ToolExecutionResponse | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Expiry checks are performed during user actions,
  // not during React rendering.
  const [checkedAt, setCheckedAt] =
    useState<number | null>(null);

  const filename =
    typeof approval.arguments.filename === "string"
      ? approval.arguments.filename
      : "Unknown";

  const content =
    typeof approval.arguments.content === "string"
      ? approval.arguments.content
      : "";

  const expiresAt = parseBackendTimestamp(
    approval.expires_at
  ).getTime();

  const expired =
    checkedAt !== null &&
    (!Number.isFinite(expiresAt) ||
      expiresAt <= checkedAt);

  async function refreshApproval() {
    setBusy(true);
    setError("");

    try {
      const updated = await getToolApproval(approval.id);

      setApproval(updated);
      setCheckedAt(Date.now());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not refresh approval."
      );
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: "approve" | "deny") {
    if (isApprovalExpired(approval.expires_at)) {
      setCheckedAt(Date.now());
      setError(
        "This approval has expired. Create a new request."
      );
      return;
    }

    setBusy(true);
    setError("");

    try {
      if (action === "approve") {
        await approveToolApproval(approval.id);
      } else {
        await denyToolApproval(approval.id);
      }

      const updated = await getToolApproval(approval.id);

      setApproval(updated);
      setCheckedAt(Date.now());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Approval decision failed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function execute() {
    if (isApprovalExpired(approval.expires_at)) {
      setCheckedAt(Date.now());
      setError(
        "This approval has expired. Create a new request."
      );
      return;
    }

    if (
      !window.confirm(
        `Create "${filename}" with the displayed content?`
      )
    ) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const result = await executeToolApproval(approval.id);

      setExecution(result);

      const updated = await getToolApproval(approval.id);

      setApproval(updated);
      setCheckedAt(Date.now());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Execution failed."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="w-full max-w-xl space-y-4 rounded-2xl border border-blue-200 bg-white p-5 text-gray-900 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">
          Secure File Approval
        </h3>

        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
          {approval.status}
        </span>
      </div>

      <p className="text-sm text-gray-600">
        ORVYN will not create this file without your
        approval and a separate execution step.
      </p>

      <div className="rounded-lg bg-gray-50 p-3">
        <p className="text-xs text-gray-500">
          Filename
        </p>

        <p className="mt-1 break-all text-sm font-semibold">
          {filename}
        </p>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-gray-600">
          Exact file content
        </p>

        <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all rounded-lg border bg-gray-50 p-3 text-xs">
          {content}
        </pre>
      </div>

      <p className="text-xs text-gray-500">
        Expires: {formatExpiry(approval.expires_at)}
      </p>

      {expired &&
        (approval.status === "pending" ||
          approval.status === "approved") && (
          <p className="text-sm text-amber-700">
            This approval has expired.
            Create a new request.
          </p>
        )}

      {error && (
        <div
          role="alert"
          className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {approval.status === "pending" && !expired && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void decide("approve")}
            className="rounded-lg bg-green-700 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Approve
          </button>

          <button
            type="button"
            disabled={busy}
            onClick={() => void decide("deny")}
            className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50"
          >
            Deny
          </button>
        </div>
      )}

      {approval.status === "approved" && !expired && (
        <button
          type="button"
          disabled={busy}
          onClick={() => void execute()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Execute Approved Action
        </button>
      )}

      {approval.status === "denied" && (
        <p className="text-sm text-gray-600">
          Request denied.
          This approval cannot be executed.
        </p>
      )}

      {approval.status === "consumed" && (
        <p className="text-sm text-green-700">
          Approval consumed.
          This approval cannot be reused.
        </p>
      )}

      {execution && (
        <div className="rounded-lg border p-3">
          <p className="text-sm font-semibold">
            Execution status: {execution.status}
          </p>

          <pre className="mt-2 overflow-auto whitespace-pre-wrap break-all text-xs">
            {JSON.stringify(
              execution.output ?? execution.error ?? {},
              null,
              2
            )}
          </pre>
        </div>
      )}

      <div className="flex flex-wrap gap-4 text-xs">
        <button
          type="button"
          disabled={busy}
          onClick={() => void refreshApproval()}
          className="text-blue-700 underline disabled:opacity-50"
        >
          Refresh Status
        </button>

        <Link
          href="/tool-approvals"
          className="text-blue-700 underline"
        >
          Approval Dashboard
        </Link>
      </div>
    </article>
  );
}
