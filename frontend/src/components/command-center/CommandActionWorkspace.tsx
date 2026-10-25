
"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  CommandActionResult,
  ParsedCommand,
} from "@/types/commandAction";

import { parseCommand } from "@/services/commandParser";
import { coordinateCommandExecution } from "@/services/commandExecutionCoordinator";
import { useCommandHistory } from "@/hooks/useCommandHistory";
import {
  searchYouTubeVideos,
  type YouTubeVideo,
} from "@/services/youtubeService";

import CommandConfirmationDialog from "@/components/command-center/CommandConfirmationDialog";
import CommandPreviewCard from "@/components/command-center/CommandPreviewCard";
import CommandStatusBadge from "@/components/command-center/CommandStatusBadge";
import CommandActivityFeed from "@/components/command-center/CommandActivityFeed";
import CommandInsightsSection from "@/components/command-center/CommandInsightsSection";

interface CommandActionWorkspaceProps {
  command?: string;
  onCommandChange?: (value: string) => void;
  onOpenChat?: () => void;
  onSpeak?: (text: string) => void;
}

function createResult(
  command: ParsedCommand,
  status: CommandActionResult["status"],
  message: string,
): CommandActionResult {
  return {
    commandId: command.id,
    status,
    message,
    completedAt: new Date().toISOString(),
  };
}

export default function CommandActionWorkspace({
  command: externalCommand,
  onCommandChange,
  onOpenChat,
  onSpeak,
}: CommandActionWorkspaceProps) {
  const [draft, setDraft] = useState(externalCommand ?? "");
  const [preparedCommand, setPreparedCommand] =
    useState<ParsedCommand | null>(null);
  const [result, setResult] =
    useState<CommandActionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [videoResults, setVideoResults] = useState<YouTubeVideo[]>([]);
  const [selectedVideo, setSelectedVideo] =
    useState<YouTubeVideo | null>(null);
  const [videoSearchQuery, setVideoSearchQuery] = useState("");

  const { history, recordCommand, clearHistory } = useCommandHistory();

  const clearVideoResults = useCallback(() => {
    setVideoResults([]);
    setSelectedVideo(null);
    setVideoSearchQuery("");
  }, []);

  useEffect(() => {
    if (externalCommand !== undefined) {
      setDraft(externalCommand);
      setPreparedCommand(null);
      setResult(null);
      setError(null);
      clearVideoResults();
    }
  }, [externalCommand, clearVideoResults]);

  const updateDraft = useCallback(
    (value: string) => {
      setDraft(value);
      onCommandChange?.(value);
      setPreparedCommand(null);
      setResult(null);
      setError(null);
      clearVideoResults();
    },
    [onCommandChange, clearVideoResults],
  );

  const canPrepare = useMemo(
    () =>
      draft.trim().length > 0 &&
      draft.trim().length <= 1000 &&
      !busy,
    [draft, busy],
  );

  const prepareCommand = useCallback(() => {
    const cleaned = draft.trim();

    if (!cleaned) {
      setError("Enter a command before continuing.");
      return;
    }

    if (cleaned.length > 1000) {
      setError("Commands must be 1000 characters or fewer.");
      return;
    }

    try {
      const parsed = parseCommand(cleaned);
      setPreparedCommand(parsed);
      setResult(null);
      setError(null);
      clearVideoResults();
    } catch {
      setPreparedCommand(null);
      setError(
        "ORVYN could not understand this command. Try rephrasing it.",
      );
    }
  }, [draft, clearVideoResults]);

  const runCommand = useCallback(
    async (parsed: ParsedCommand, confirmed: boolean) => {
      if (busy) return;

      setBusy(true);
      setError(null);

      try {
        // Open the existing Chat Workspace for chat-related commands.
        if (parsed.kind === "chat_request") {
          if (!onOpenChat) {
            const blocked = createResult(
              parsed,
              "blocked",
              "Chat Workspace is not connected to this command handler.",
            );

            setResult(blocked);
            recordCommand(parsed, blocked);
            return;
          }

          onOpenChat();

          const opened = createResult(
            parsed,
            "success",
            "Chat Workspace opened. Submit your message there to receive an AI response.",
          );

          setResult(opened);
          recordCommand(parsed, opened);
          onSpeak?.("Chat Workspace is ready.");
          return;
        }

        // Run YouTube searches through the secure FastAPI backend.
        if (parsed.kind === "youtube_search") {
          const query =
            parsed.query?.trim() || parsed.originalText.trim();

          setVideoSearchQuery(query);
          setVideoResults([]);
          setSelectedVideo(null);

          const response = await searchYouTubeVideos(query, 10);
          setVideoResults(response.videos);

          if (response.videos.length === 0) {
            const noResults = createResult(
              parsed,
              "failed",
              `No YouTube videos were found for "${query}". Try another search.`,
            );

            setResult(noResults);
            recordCommand(parsed, noResults);
            onSpeak?.(noResults.message);
            return;
          }

          const firstVideo = response.videos[0];
          setSelectedVideo(firstVideo);

          const success = createResult(
            parsed,
            "success",
            `Found ${response.videos.length} YouTube videos for "${query}". The first video is loaded in the player. If autoplay is blocked, press Play in the player.`,
          );

          setResult(success);
          recordCommand(parsed, success);
          onSpeak?.(
            `I found videos for ${query}. The first video is ready in the player.`,
          );
          return;
        }

        // Preserve the existing policy, confirmation, and browser-action flow.
        const execution = await coordinateCommandExecution(parsed, {
          confirmed,
        });

        setResult(execution);

        if (execution.status === "pending") {
          setConfirmationOpen(true);
          return;
        }

        setConfirmationOpen(false);
        recordCommand(parsed, execution);

        if (execution.status === "success") {
          onSpeak?.(execution.message);
        }
      } catch (caught: unknown) {
        const message =
          caught instanceof Error
            ? caught.message
            : "The command failed unexpectedly.";

        setError(message);

        const failed = createResult(
          parsed,
          "failed",
          message,
        );

        setResult(failed);
        recordCommand(parsed, failed);
      } finally {
        setBusy(false);
      }
    },
    [busy, onOpenChat, onSpeak, recordCommand],
  );

  const executePreparedCommand = useCallback(() => {
    if (!preparedCommand) return;
    void runCommand(preparedCommand, false);
  }, [preparedCommand, runCommand]);

  const confirmAction = useCallback(() => {
    if (!preparedCommand || busy) return;

    setConfirmationOpen(false);
    void runCommand(preparedCommand, true);
  }, [preparedCommand, busy, runCommand]);

  const cancelAction = useCallback(() => {
    if (busy) return;

    setConfirmationOpen(false);

    if (preparedCommand) {
      const cancelled = createResult(
        preparedCommand,
        "blocked",
        "Action cancelled by the user. No browser action was initiated.",
      );

      setResult(cancelled);
      recordCommand(preparedCommand, cancelled);
    }
  }, [busy, preparedCommand, recordCommand]);

  const resetWorkspace = useCallback(() => {
    if (busy) return;

    setDraft("");
    onCommandChange?.("");
    setPreparedCommand(null);
    setResult(null);
    setError(null);
    setConfirmationOpen(false);
    clearVideoResults();
  }, [busy, onCommandChange, clearVideoResults]);

  const playerUrl = selectedVideo
    ? `${selectedVideo.embed_url}?autoplay=1&playsinline=1&rel=0`
    : "";

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-cyan-400/20 bg-[#071020] p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300/70">
              ORVYN / Command Engine
            </p>

            <h2 className="mt-2 text-xl font-semibold text-white">
              Command &amp; Action Workspace
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Describe an action naturally. ORVYN prepares a command
              preview before running a supported action.
              YouTube searches use the ORVYN backend.
            </p>
          </div>

          <span className="rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-1.5 text-xs text-emerald-300">
            Local command engine
          </span>
        </div>

        <label
          htmlFor="orvyn-command-workspace-input"
          className="mt-6 block text-sm font-medium text-slate-300"
        >
          What would you like ORVYN to do?
        </label>

        <textarea
          id="orvyn-command-workspace-input"
          value={draft}
          onChange={(event) => updateDraft(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              (event.ctrlKey || event.metaKey)
            ) {
              event.preventDefault();
              prepareCommand();
            }
          }}
          maxLength={1000}
          rows={4}
          placeholder="YouTube par Arijit Singh ke songs chalao"
          disabled={busy}
          className="mt-2 w-full resize-y rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-400 disabled:opacity-60"
        />

        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            Ctrl + Enter to prepare · {draft.length}/1000 characters
          </p>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={resetWorkspace}
              disabled={
                busy ||
                (!draft && !result && !preparedCommand && videoResults.length === 0)
              }
              className="rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-300 transition hover:bg-white/5 disabled:opacity-40"
            >
              Reset
            </button>

            <button
              type="button"
              onClick={prepareCommand}
              disabled={!canPrepare}
              className="rounded-xl bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Prepare command
            </button>
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/5 p-3 text-sm text-rose-300"
          >
            {error}
          </p>
        )}
      </section>

      <CommandPreviewCard
        command={preparedCommand}
        busy={busy}
        onEdit={() => {
          setPreparedCommand(null);
          setResult(null);
        }}
        onExecute={executePreparedCommand}
      />

      {busy && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4"
        >
          <div className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-300" />
            <div>
              <p className="text-sm font-medium text-cyan-200">
                Processing command
              </p>
              <p className="mt-1 text-xs text-slate-400">
                ORVYN is waiting for the action handler.
              </p>
            </div>
          </div>
        </div>
      )}

      {result && (
        <section
          aria-live="polite"
          className="rounded-2xl border border-white/10 bg-slate-950/50 p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-white">
              Execution result
            </h3>
            <CommandStatusBadge status={result.status} />
          </div>

          <p className="mt-3 break-words text-sm leading-6 text-slate-300">
            {result.message}
          </p>

          <p className="mt-3 text-xs text-slate-500">
            {new Date(result.completedAt).toLocaleString()}
          </p>
        </section>
      )}

      {videoResults.length > 0 && (
        <section className="space-y-4 rounded-2xl border border-cyan-400/20 bg-[#071020] p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300/70">
                ORVYN / YouTube
              </p>
              <h3 className="mt-1 text-lg font-semibold text-white">
                Music &amp; Video Player
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                Results for: {videoSearchQuery}
              </p>
            </div>

            <span className="rounded-full border border-cyan-400/20 px-3 py-1 text-xs text-cyan-200">
              {videoResults.length} results
            </span>
          </div>

          {selectedVideo && (
            <div className="space-y-3">
              <div className="aspect-video overflow-hidden rounded-xl border border-slate-800 bg-black">
                <iframe
                  key={selectedVideo.video_id}
                  src={playerUrl}
                  title={`YouTube player: ${selectedVideo.title}`}
                  className="h-full w-full"
                  allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
                  referrerPolicy="strict-origin-when-cross-origin"
                  allowFullScreen
                />
              </div>

              <div>
                <h4 className="font-medium leading-6 text-white">
                  {selectedVideo.title}
                </h4>
                <p className="mt-1 text-sm text-slate-400">
                  {selectedVideo.channel_title}
                </p>
                <a
                  href={selectedVideo.watch_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-sm text-cyan-300 underline underline-offset-4 hover:text-cyan-200"
                >
                  Open on YouTube
                </a>
              </div>

              <p className="text-xs leading-5 text-slate-500">
                If autoplay is blocked by your browser or YouTube,
                press Play inside the player. Some videos may not allow
                embedding.
              </p>
            </div>
          )}

          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-slate-300">
              Search results
            </h4>

            {videoResults.map((video) => {
              const isSelected =
                selectedVideo?.video_id === video.video_id;

              return (
                <button
                  key={video.video_id}
                  type="button"
                  onClick={() => setSelectedVideo(video)}
                  className={`flex w-full items-center gap-3 rounded-xl border p-2 text-left transition ${
                    isSelected
                      ? "border-cyan-400/60 bg-cyan-400/10"
                      : "border-slate-800 bg-slate-900/70 hover:border-slate-600"
                  }`}
                >
                  {video.thumbnail_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={video.thumbnail_url}
                      alt=""
                      loading="lazy"
                      className="h-16 w-28 shrink-0 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="flex h-16 w-28 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-cyan-300">
                      ▶
                    </div>
                  )}

                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 block text-sm font-medium text-slate-100">
                      {video.title}
                    </span>
                    <span className="mt-1 block truncate text-xs text-slate-400">
                      {video.channel_title}
                    </span>
                  </span>

                  <span className="px-2 text-sm text-cyan-300">
                    {isSelected ? "Selected" : "Play"}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <CommandActivityFeed
        entries={history}
        onClear={clearHistory}
        limit={8}
      />

      <div className="mt-6">
        <CommandInsightsSection />
      </div>

      <CommandConfirmationDialog
        open={confirmationOpen}
        title="Confirm external action"
        description={
          preparedCommand
            ? `ORVYN is preparing to perform: ${preparedCommand.title}. ${preparedCommand.description} Continue only if you recognise and trust this destination.`
            : "Confirm this action before proceeding."
        }
        confirmLabel="Confirm and continue"
        busy={busy}
        onConfirm={confirmAction}
        onCancel={cancelAction}
      />
    </div>
  );
}
