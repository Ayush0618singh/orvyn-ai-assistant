
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  createAgentPlan,
  getAgentPlan,
  getAgentPlans,
} from "@/services/agentPlanService";
import { getConversations } from "@/services/conversationService";

import type {
  AgentPlanDetail,
  AgentPlanSummary,
} from "@/types/agentPlan";
import type { ConversationSummary } from "@/types/conversation";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown date"
    : date.toLocaleString();
}

function statusClass(status: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "failed":
    case "cancelled":
      return "border-red-500/30 bg-red-500/10 text-red-300";
    case "awaiting_approval":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "running":
      return "border-cyan-500/30 bg-cyan-500/10 text-cyan-300";
    default:
      return "border-slate-600 bg-slate-800 text-slate-300";
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export default function AgentWorkspacePage() {
  const [plans, setPlans] = useState<AgentPlanSummary[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<AgentPlanDetail | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [taskRequest, setTaskRequest] = useState("");

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const mountedRef = useRef(false);
  const loadRequestRef = useRef(0);
  const detailRequestRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      loadRequestRef.current += 1;
      detailRequestRef.current += 1;
    };
  }, []);

  const loadWorkspace = useCallback(async () => {
    const requestId = ++loadRequestRef.current;

    setLoading(true);
    setError(null);

    try {
      const [planResponse, conversationResponse] = await Promise.all([
        getAgentPlans(50, 0),
        getConversations(),
      ]);

      if (!mountedRef.current || requestId !== loadRequestRef.current) {
        return;
      }

      setPlans(planResponse.items);
      setTotal(planResponse.total);
      setConversations(conversationResponse);

      setSelectedConversationId((current) => {
        if (conversationResponse.some((item) => item.id === current)) {
          return current;
        }
        return conversationResponse[0]?.id ?? "";
      });

      setSelectedPlan((current) => {
        if (!current) return null;
        const stillExists = planResponse.items.some(
          (plan) => plan.id === current.id
        );
        return stillExists ? current : null;
      });
    } catch (err) {
      if (!mountedRef.current || requestId !== loadRequestRef.current) {
        return;
      }

      setError(getErrorMessage(err, "Unable to load Agent Workspace."));
    } finally {
      if (mountedRef.current && requestId === loadRequestRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  async function openPlan(planId: string) {
    const requestId = ++detailRequestRef.current;

    setDetailLoading(true);
    setError(null);
    setNotice(null);

    try {
      const detail = await getAgentPlan(planId);

      if (!mountedRef.current || requestId !== detailRequestRef.current) {
        return;
      }

      setSelectedPlan(detail);
    } catch (err) {
      if (!mountedRef.current || requestId !== detailRequestRef.current) {
        return;
      }

      setError(getErrorMessage(err, "Unable to load agent plan."));
    } finally {
      if (mountedRef.current && requestId === detailRequestRef.current) {
        setDetailLoading(false);
      }
    }
  }

  async function handleCreatePlan(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const request = taskRequest.trim();

    if (creating || !selectedConversationId || !request) return;

    setCreating(true);
    setError(null);
    setNotice(null);

    try {
      const created = await createAgentPlan({
        conversation_id: selectedConversationId,
        request,
      });

      if (!mountedRef.current) return;

      setSelectedPlan(created);
      setTaskRequest("");
      setNotice("Task plan saved. No tools were executed by creating this plan.");

      await loadWorkspace();

      if (mountedRef.current) {
        setSelectedPlan(created);
      }
    } catch (err) {
      if (!mountedRef.current) return;

      setError(getErrorMessage(err, "Unable to create plan."));
    } finally {
      if (mountedRef.current) setCreating(false);
    }
  }

  const approvalSteps =
    selectedPlan?.steps.filter((step) => step.requires_approval).length ?? 0;

  return (
    <div className="min-h-screen bg-[#050b18] text-slate-100">
      <header className="border-b border-cyan-500/20 bg-[#081326]">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link
              href="/command-center"
              className="text-sm text-cyan-400 hover:text-cyan-300"
            >
              ← Back to Command Center
            </Link>

            <h1 className="mt-2 text-2xl font-bold tracking-wide">
              ORVYN
              <span className="ml-3 text-sm font-normal text-cyan-400">
                AGENT WORKSPACE
              </span>
            </h1>

            <p className="mt-1 text-sm text-slate-400">
              Secure planning, task visibility and approval-aware workflows
            </p>
          </div>

          <div className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-cyan-300">
            Planning Mode
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-5 py-8">
        <section className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Total Plans
            </p>
            <p className="mt-2 text-3xl font-bold text-cyan-300">
              {loading && total === null ? "…" : total ?? "—"}
            </p>
          </div>

          <div className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Available Conversations
            </p>
            <p className="mt-2 text-3xl font-bold text-cyan-300">
              {loading ? "…" : conversations.length}
            </p>
          </div>

          <div className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Selected Plan Steps
            </p>
            <p className="mt-2 text-3xl font-bold text-cyan-300">
              {selectedPlan?.steps.length ?? 0}
            </p>
          </div>
        </section>

        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => void loadWorkspace()}
              className="rounded-lg border border-red-400/30 px-3 py-2 hover:bg-red-500/10"
            >
              Retry
            </button>
          </div>
        )}

        {notice && (
          <div
            role="status"
            className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 text-sm text-cyan-200"
          >
            {notice}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-6">
            <section className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
              <h2 className="text-lg font-semibold">Create Task Plan</h2>
              <p className="mt-2 text-sm text-slate-400">
                A saved plan does not automatically execute tools.
              </p>

              <form onSubmit={handleCreatePlan} className="mt-5 space-y-4">
                <div>
                  <label
                    htmlFor="agent-conversation"
                    className="mb-2 block text-sm text-slate-300"
                  >
                    Conversation
                  </label>

                  <select
                    id="agent-conversation"
                    value={selectedConversationId}
                    onChange={(event) =>
                      setSelectedConversationId(event.target.value)
                    }
                    disabled={loading || creating}
                    required
                    className="w-full rounded-xl border border-slate-700 bg-[#071020] px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-400 disabled:opacity-60"
                  >
                    <option value="">Select a conversation</option>
                    {conversations.map((conversation) => (
                      <option key={conversation.id} value={conversation.id}>
                        {conversation.title}
                      </option>
                    ))}
                  </select>

                  {conversations.length === 0 && !loading && (
                    <p className="mt-2 text-xs text-amber-300">
                      Create a conversation in AI Chat first.
                    </p>
                  )}
                </div>

                <div>
                  <label
                    htmlFor="agent-request"
                    className="mb-2 block text-sm text-slate-300"
                  >
                    Task Request
                  </label>

                  <textarea
                    id="agent-request"
                    value={taskRequest}
                    onChange={(event) => setTaskRequest(event.target.value)}
                    maxLength={8192}
                    rows={6}
                    required
                    placeholder="Describe the task you want ORVYN to plan..."
                    className="w-full resize-y rounded-xl border border-slate-700 bg-[#071020] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-cyan-400"
                  />

                  <p className="mt-1 text-right text-xs text-slate-500">
                    {taskRequest.length}/8192
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={
                    creating ||
                    loading ||
                    !selectedConversationId ||
                    !taskRequest.trim()
                  }
                  className="w-full rounded-xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-[#04101d] transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {creating ? "Creating Plan..." : "Create Secure Plan"}
                </button>
              </form>
            </section>

            <section className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Plan History</h2>
                <button
                  type="button"
                  onClick={() => void loadWorkspace()}
                  disabled={loading}
                  className="text-xs font-medium text-cyan-400 hover:text-cyan-300 disabled:opacity-40"
                >
                  {loading ? "Loading..." : "↻ Refresh"}
                </button>
              </div>

              <div className="mt-4 max-h-[480px] space-y-3 overflow-y-auto">
                {loading && (
                  <p className="text-sm text-slate-400">Loading plans...</p>
                )}

                {!loading && !error && plans.length === 0 && (
                  <p className="text-sm text-slate-400">
                    No plans found for this account.
                  </p>
                )}

                {plans.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => void openPlan(plan.id)}
                    disabled={detailLoading}
                    className={`w-full rounded-xl border p-4 text-left transition hover:border-cyan-500/50 disabled:opacity-50 ${
                      selectedPlan?.id === plan.id
                        ? "border-cyan-500/60 bg-cyan-500/10"
                        : "border-slate-700 bg-[#071020]"
                    }`}
                  >
                    <p className="line-clamp-2 text-sm font-medium">
                      {plan.original_request}
                    </p>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <span
                        className={`rounded-full border px-2 py-1 text-xs ${statusClass(plan.status)}`}
                      >
                        {plan.status.replaceAll("_", " ")}
                      </span>
                      <span className="text-xs text-slate-500">
                        {formatDate(plan.created_at)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </div>

          <section className="min-h-[600px] rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5 sm:p-7">
            {detailLoading ? (
              <div className="flex min-h-[500px] items-center justify-center text-sm text-slate-400">
                Loading plan details...
              </div>
            ) : !selectedPlan ? (
              <div className="flex min-h-[500px] flex-col items-center justify-center text-center">
                <div className="mb-5 flex h-24 w-24 items-center justify-center rounded-full border border-cyan-400/40 bg-cyan-500/10 text-4xl text-cyan-300 shadow-[0_0_50px_rgba(34,211,238,0.15)]">
                  ◈
                </div>
                <h2 className="text-xl font-semibold">Agent Planning Console</h2>
                <p className="mt-3 max-w-md text-sm leading-6 text-slate-400">
                  Create a plan or select an existing plan to inspect its steps,
                  dependencies and approval requirements.
                </p>
              </div>
            ) : (
              <div>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
                      Task Planning Blueprint
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">Agent Plan</h2>
                  </div>
                  <span
                    className={`rounded-full border px-3 py-2 text-xs ${statusClass(selectedPlan.status)}`}
                  >
                    {selectedPlan.status.replaceAll("_", " ")}
                  </span>
                </div>

                <div className="mt-6 rounded-xl border border-slate-700 bg-[#071020] p-5">
                  <p className="text-xs uppercase tracking-wider text-slate-500">
                    Original Request
                  </p>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">
                    {selectedPlan.original_request}
                  </p>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-700 p-4">
                    <p className="text-xs text-slate-400">Total Steps</p>
                    <p className="mt-2 text-2xl font-bold text-cyan-300">
                      {selectedPlan.steps.length}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-700 p-4">
                    <p className="text-xs text-slate-400">Approval Required</p>
                    <p className="mt-2 text-2xl font-bold text-amber-300">
                      {approvalSteps}
                    </p>
                  </div>
                </div>

                <div className="mt-8">
                  <h3 className="text-lg font-semibold">Planned Workflow</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    Review each planned step and its approval requirements.
                  </p>

                  <div className="mt-6 space-y-4">
                    {selectedPlan.steps.map((step, index) => (
                      <article
                        key={step.id}
                        className="rounded-xl border border-slate-700 bg-[#071020] p-5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                            Step {step.position ?? index + 1}
                          </span>
                          <span
                            className={`rounded-full border px-2 py-1 text-xs ${statusClass(step.status)}`}
                          >
                            {step.status.replaceAll("_", " ")}
                          </span>
                        </div>

                        <h4 className="mt-3 text-sm font-semibold capitalize text-slate-100">
                          {step.kind.replaceAll("_", " ")}
                        </h4>
                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {step.description}
                        </p>

                        <div className="mt-4 flex flex-wrap gap-2">
                          {step.requires_approval ? (
                            <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300">
                              Explicit Approval Required
                            </span>
                          ) : (
                            <span className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400">
                              No Approval Required
                            </span>
                          )}

                          {step.depends_on.length > 0 && (
                            <span className="rounded-lg border border-cyan-500/20 px-3 py-1 text-xs text-cyan-300">
                              {step.depends_on.length} Dependencies
                            </span>
                          )}
                        </div>
                      </article>
                    ))}

                    {selectedPlan.steps.length === 0 && (
                      <p className="rounded-xl border border-slate-700 p-4 text-sm text-slate-400">
                        This plan currently has no steps.
                      </p>
                    )}
                  </div>
                </div>

                <div className="mt-8 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-sm leading-6 text-slate-300">
                  This view displays the saved plan. Creating or viewing a plan
                  does not execute tools. Any sensitive action must go through
                  server-side authorization and the existing approval workflow.
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
