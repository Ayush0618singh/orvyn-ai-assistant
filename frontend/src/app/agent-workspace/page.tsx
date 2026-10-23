
"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  createAgentPlan,
  getAgentPlan,
  getAgentPlans,
} from "@/services/agentPlanService";

import {
  getConversations,
} from "@/services/conversationService";

import type {
  AgentPlanDetail,
  AgentPlanSummary,
} from "@/types/agentPlan";

import type {
  ConversationSummary,
} from "@/types/conversation";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return date.toLocaleString();
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

export default function AgentWorkspacePage() {
  const [plans, setPlans] = useState<
    AgentPlanSummary[]
  >([]);

  const [
    conversations,
    setConversations,
  ] = useState<ConversationSummary[]>([]);

  const [
    selectedPlan,
    setSelectedPlan,
  ] = useState<AgentPlanDetail | null>(
    null
  );

  const [
    selectedConversationId,
    setSelectedConversationId,
  ] = useState("");

  const [
    taskRequest,
    setTaskRequest,
  ] = useState("");

  const [loading, setLoading] =
    useState(true);

  const [creating, setCreating] =
    useState(false);

  const [detailLoading, setDetailLoading] =
    useState(false);

  const [error, setError] = useState<
    string | null
  >(null);

  const [notice, setNotice] = useState<
    string | null
  >(null);

  const [total, setTotal] = useState(0);

  const loadWorkspace = useCallback(
    async () => {
      setLoading(true);
      setError(null);

      try {
        const [
          planResponse,
          conversationResponse,
        ] = await Promise.all([
          getAgentPlans(50, 0),
          getConversations(),
        ]);

        setPlans(planResponse.items);
        setTotal(planResponse.total);
        setConversations(
          conversationResponse
        );

        setSelectedConversationId(
          (current) => {
            if (
              conversationResponse.some(
                (conversation) =>
                  conversation.id === current
              )
            ) {
              return current;
            }

            return (
              conversationResponse[0]?.id ??
              ""
            );
          }
        );
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load Agent Workspace."
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
  let cancelled = false;

  async function initializeWorkspace() {
    try {
      const [
        planResponse,
        conversationResponse,
      ] = await Promise.all([
        getAgentPlans(50, 0),
        getConversations(),
      ]);

      if (cancelled) return;

      setPlans(planResponse.items);
      setTotal(planResponse.total);
      setConversations(conversationResponse);

      setSelectedConversationId(
        (current) => {
          const exists =
            conversationResponse.some(
              (conversation) =>
                conversation.id === current
            );

          return exists
            ? current
            : (conversationResponse[0]?.id ?? "");
        }
      );
    } catch (err) {
      if (cancelled) return;

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load Agent Workspace."
      );
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  }

  void initializeWorkspace();

  return () => {
    cancelled = true;
  };
}, []);

  async function openPlan(
    planId: string
  ) {
    setDetailLoading(true);
    setError(null);

    try {
      const detail =
        await getAgentPlan(planId);

      setSelectedPlan(detail);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load agent plan."
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleCreatePlan(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (
      creating ||
      !selectedConversationId ||
      !taskRequest.trim()
    ) {
      return;
    }

    setCreating(true);
    setError(null);
    setNotice(null);

    try {
      const created =
        await createAgentPlan({
          conversation_id:
            selectedConversationId,
          request: taskRequest.trim(),
        });

      setSelectedPlan(created);
      setTaskRequest("");

      setNotice(
        "Task plan saved successfully. No tools have been executed."
      );

      const updated =
        await getAgentPlans(50, 0);

      setPlans(updated.items);
      setTotal(updated.total);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create plan."
      );
    } finally {
      setCreating(false);
    }
  }

  const approvalSteps =
    selectedPlan?.steps.filter(
      (step) =>
        step.requires_approval
    ).length ?? 0;

  return (
    <div className="min-h-screen bg-[#050b18] text-slate-100">
      {/* HEADER */}

      <header className="border-b border-cyan-500/20 bg-[#081326]">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5">
          <div>
            <Link
              href="/"
              className="text-sm text-cyan-400 hover:text-cyan-300"
            >
              ← Back to ORVYN
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
        {/* STATS */}

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Total Plans
            </p>

            <p className="mt-2 text-3xl font-bold text-cyan-300">
              {total}
            </p>
          </div>

          <div className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Available Conversations
            </p>

            <p className="mt-2 text-3xl font-bold text-cyan-300">
              {conversations.length}
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
        </div>

        {/* ERROR / NOTICE */}

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          >
            {error}
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
          {/* LEFT PANEL */}

          <div className="space-y-6">
            {/* CREATE PLAN */}

            <section className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
              <h2 className="text-lg font-semibold">
                Create Task Plan
              </h2>

              <p className="mt-2 text-sm text-slate-400">
                Plans are stored in your selected conversation. Creating a plan does not execute tools.
              </p>

              <form
                onSubmit={handleCreatePlan}
                className="mt-5 space-y-4"
              >
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
                      setSelectedConversationId(
                        event.target.value
                      )
                    }
                    className="w-full rounded-xl border border-slate-700 bg-[#071020] px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-400"
                  >
                    {conversations.length === 0 && (
                      <option value="">
                        No conversations available
                      </option>
                    )}

                    {conversations.map(
                      (conversation) => (
                        <option
                          key={conversation.id}
                          value={conversation.id}
                        >
                          {conversation.title}
                        </option>
                      )
                    )}
                  </select>
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
                    onChange={(event) =>
                      setTaskRequest(
                        event.target.value
                      )
                    }
                    maxLength={8192}
                    rows={6}
                    placeholder="Create a Python interview study plan, save it in a file, and summarize the result."
                    className="w-full resize-y rounded-xl border border-slate-700 bg-[#071020] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-cyan-400"
                  />
                </div>

                <button
                  type="submit"
                  disabled={
                    creating ||
                    !selectedConversationId ||
                    !taskRequest.trim()
                  }
                  className="w-full rounded-xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-[#04101d] transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {creating
                    ? "Creating Plan..."
                    : "Create Secure Plan"}
                </button>
              </form>
            </section>

            {/* PLAN HISTORY */}

            <section className="rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">
                  Plan History
                </h2>

                <button
                  type="button"
                  onClick={() =>
                    void loadWorkspace()
                  }
                  disabled={loading}
                  className="text-xs font-medium text-cyan-400 hover:text-cyan-300 disabled:opacity-40"
                >
                  Refresh
                </button>
              </div>

              <div className="mt-4 max-h-[480px] space-y-3 overflow-y-auto">
                {loading && (
                  <p className="text-sm text-slate-400">
                    Loading plans...
                  </p>
                )}

                {!loading &&
                  plans.length === 0 && (
                    <p className="text-sm text-slate-400">
                      No plans created yet.
                    </p>
                  )}

                {plans.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() =>
                      void openPlan(plan.id)
                    }
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
                        className={`rounded-full border px-2 py-1 text-xs ${statusClass(
                          plan.status
                        )}`}
                      >
                        {plan.status}
                      </span>

                      <span className="text-xs text-slate-500">
                        {formatDate(
                          plan.created_at
                        )}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </div>

          {/* RIGHT PANEL */}

          <section className="min-h-[600px] rounded-2xl border border-cyan-500/20 bg-[#0b1930] p-5 sm:p-7">
            {!selectedPlan ? (
              <div className="flex h-full min-h-[500px] flex-col items-center justify-center text-center">
                <div className="mb-5 flex h-24 w-24 items-center justify-center rounded-full border border-cyan-400/40 bg-cyan-500/10 text-4xl text-cyan-300 shadow-[0_0_50px_rgba(34,211,238,0.15)]">
                  ◈
                </div>

                <h2 className="text-xl font-semibold">
                  Agent Planning Console
                </h2>

                <p className="mt-3 max-w-md text-sm leading-6 text-slate-400">
                  Create a new plan or select an existing one to inspect its steps, dependencies and approval requirements.
                </p>
              </div>
            ) : (
              <div>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
                      Task Execution Blueprint
                    </p>

                    <h2 className="mt-2 text-xl font-semibold">
                      Agent Plan
                    </h2>
                  </div>

                  <span
                    className={`rounded-full border px-3 py-2 text-xs ${statusClass(
                      selectedPlan.status
                    )}`}
                  >
                    {selectedPlan.status}
                  </span>
                </div>

                <div className="mt-6 rounded-xl border border-slate-700 bg-[#071020] p-5">
                  <p className="text-xs uppercase tracking-wider text-slate-500">
                    Original Request
                  </p>

                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">
                    {
                      selectedPlan.original_request
                    }
                  </p>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-700 p-4">
                    <p className="text-xs text-slate-400">
                      Total Steps
                    </p>

                    <p className="mt-2 text-2xl font-bold text-cyan-300">
                      {
                        selectedPlan.steps.length
                      }
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-700 p-4">
                    <p className="text-xs text-slate-400">
                      Approval Required
                    </p>

                    <p className="mt-2 text-2xl font-bold text-amber-300">
                      {approvalSteps}
                    </p>
                  </div>
                </div>

                <div className="mt-8">
                  <h3 className="text-lg font-semibold">
                    Planned Workflow
                  </h3>

                  <p className="mt-1 text-sm text-slate-400">
                    Steps are listed in their planned order. Dependencies and approval requirements are shown explicitly.
                  </p>

                  <div className="mt-6 space-y-4">
                    {selectedPlan.steps.map(
                      (step, index) => (
                        <div
                          key={step.id}
                          className="relative rounded-xl border border-slate-700 bg-[#071020] p-5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                              Step {index + 1}
                            </span>

                            <span
                              className={`rounded-full border px-2 py-1 text-xs ${statusClass(
                                step.status
                              )}`}
                            >
                              {step.status}
                            </span>
                          </div>

                          <h4 className="mt-3 text-sm font-semibold capitalize text-slate-100">
                            {step.kind.replace(
                              /_/g,
                              " "
                            )}
                          </h4>

                          <p className="mt-2 text-sm leading-6 text-slate-400">
                            {
                              step.description
                            }
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

                            {step.depends_on.length >
                              0 && (
                              <span className="rounded-lg border border-cyan-500/20 px-3 py-1 text-xs text-cyan-300">
                                {
                                  step.depends_on.length
                                }{" "}
                                Dependencies
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>

                <div className="mt-8 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-sm leading-6 text-slate-300">
                  This plan is currently a saved blueprint. No files, APIs or other tools are executed automatically. Sensitive actions will use ORVYN&apos;s existing approval gateway.
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
