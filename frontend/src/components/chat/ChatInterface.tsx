
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import ChatComposer from "@/components/chat/ChatComposer";
import UnifiedAgentTimeline from "@/components/chat/UnifiedAgentTimeline";

import { useAuth } from "@/contexts/AuthContext";
import { streamChatMessage } from "@/services/api";

import {
  createConversation,
  createConversationActionMessage,
  deleteConversation,
  getConversation,
  getConversations,
  renameConversation,
} from "@/services/conversationService";

import {
  deleteAttachment,
  uploadAttachments,
} from "@/services/attachmentService";

import {
  deleteDocument,
  indexAttachment,
} from "@/services/documentService";

import {
  parseChatFileCommand,
} from "@/services/chatFileCommand";

import {
  getConversationApprovalMessageLinks,
  getConversationToolApprovals,
  requestChatWorkspaceFileApproval,
} from "@/services/chatToolApprovalService";

import {
  isSafeFileActionPlan,
  planNaturalLanguageFileAction,
} from "@/services/fileActionPlannerService";

import {
  detectPossibleFileAction,
} from "@/services/fileActionIntentService";

import {
  isValidMultilingualFileProposal,
  planMultilingualFileAction,
} from "@/services/multilingualFilePlannerService";

import type { ChatMessage } from "@/types/chat";
import type {
  ConversationSummary,
} from "@/types/conversation";

import type {
  ApprovalMessageLink,
  ToolApproval,
} from "@/types/toolApproval";

// =====================================================
// CONSTANTS
// =====================================================

const INITIAL_MESSAGE: ChatMessage = {
  id: "orvyn-welcome",
  role: "assistant",
  content:
    "Hello! Main ORVYN hoon. Aap mujhse English, Hindi ya Hinglish me baat kar sakte hain.",
  status: "completed",
  sources: [],
  web_sources: [],
};

const RAG_MIME_TYPES = new Set([
  "application/pdf",
  "text/plain",
]);

interface FileProposal {
  filename: string;
  content: string;
}

type FileResolution =
  | {
      kind: "proposal";
      proposal: FileProposal;
    }
  | {
      kind: "clarification";
      message: string;
    }
  | {
      kind: "none";
    };

function getErrorMessage(
  error: unknown,
  fallback: string
): string {
  return error instanceof Error
    ? error.message
    : fallback;
}

function isAbortError(error: unknown): boolean {
  return (
    error instanceof Error &&
    error.name === "AbortError"
  );
}

// =====================================================
// MAIN COMPONENT
// =====================================================

export default function ChatInterface() {
  const { user, logout } = useAuth();

  // ---------------------------------------------------
  // CHAT STATE
  // ---------------------------------------------------

  const [messages, setMessages] = useState<
    ChatMessage[]
  >([INITIAL_MESSAGE]);

  const [
    conversations,
    setConversations,
  ] = useState<ConversationSummary[]>([]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState<string | null>(null);

  const [
    activeTitle,
    setActiveTitle,
  ] = useState("New Chat");

  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(false);

  const [
    isLoading,
    setIsLoading,
  ] = useState(false);

  const [
    streamStarted,
    setStreamStarted,
  ] = useState(false);

  const [
    sidebarLoading,
    setSidebarLoading,
  ] = useState(true);

  const [error, setError] = useState<
    string | null
  >(null);

  const [
    webAllowed,
    setWebAllowed,
  ] = useState(true);

  // ---------------------------------------------------
  // SECURE APPROVAL STATE
  // ---------------------------------------------------

  const [
    chatFileApprovals,
    setChatFileApprovals,
  ] = useState<ToolApproval[]>([]);

  const [
    approvalMessageLinks,
    setApprovalMessageLinks,
  ] = useState<ApprovalMessageLink[]>([]);

  // ---------------------------------------------------
  // REFS
  // ---------------------------------------------------

  const bottomRef = useRef<
    HTMLDivElement | null
  >(null);

  const abortControllerRef = useRef<
    AbortController | null
  >(null);

  const conversationLoadRef = useRef(0);

  const sendLockRef = useRef(false);

  // =====================================================
  // CONVERSATION LIST
  // =====================================================

  async function loadConversationList(): Promise<
    ConversationSummary[]
  > {
    try {
      const data = await getConversations();

      setConversations(data);

      return data;
    } catch (err) {
      console.error(
        "Failed to load conversations:",
        err
      );

      return [];
    } finally {
      setSidebarLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    getConversations()
      .then((data) => {
        if (!cancelled) {
          setConversations(data);
        }
      })
      .catch((err) => {
        console.error(
          "Failed to load conversations:",
          err
        );
      })
      .finally(() => {
        if (!cancelled) {
          setSidebarLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // =====================================================
  // AUTO SCROLL
  // =====================================================

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [
    messages,
    chatFileApprovals,
    approvalMessageLinks,
    isLoading,
    error,
  ]);

  // =====================================================
  // RESET CHAT
  // =====================================================

  function resetChatView() {
    conversationLoadRef.current += 1;

    setActiveConversationId(null);
    setActiveTitle("New Chat");

    setMessages([INITIAL_MESSAGE]);

    setChatFileApprovals([]);
    setApprovalMessageLinks([]);

    setError(null);
    setSidebarOpen(false);
  }

  // =====================================================
  // SECURE FILE APPROVAL CREATION
  // =====================================================

  async function createFileApproval(
    proposal: FileProposal,
    originalUserRequest: string
  ): Promise<void> {
    const cleanedRequest =
      originalUserRequest.trim();

    if (
      !cleanedRequest ||
      cleanedRequest.length > 8192
    ) {
      throw new Error(
        "Invalid file-action message."
      );
    }

    let conversationId = activeConversationId;

    // Step 1:
    // Create conversation if none exists.

    if (!conversationId) {
      const conversation =
        await createConversation(
          `File: ${proposal.filename}`
        );

      conversationId = conversation.id;

      setActiveConversationId(
        conversation.id
      );

      setActiveTitle(
        conversation.title
      );

      await loadConversationList();
    }

    // Step 2:
    // Persist the original user request.
    // This does not execute a tool.

    const savedMessage =
      await createConversationActionMessage(
        conversationId,
        cleanedRequest
      );

    // Step 3:
    // Display persisted message with real DB ID.

    setMessages((current) => {
      if (
        current.some(
          (message) =>
            message.id === savedMessage.id
        )
      ) {
        return current;
      }

      const existingMessages =
        current.filter(
          (message) =>
            message.id !== INITIAL_MESSAGE.id
        );

      return [
        ...existingMessages,
        savedMessage,
      ];
    });

    // Step 4:
    // Request approval linked to this exact message.
    // No automatic execution.

    const approval =
      await requestChatWorkspaceFileApproval({
        conversation_id: conversationId,
        message_id: savedMessage.id,
        filename: proposal.filename,
        content: proposal.content,
      });

    // Step 5:
    // Update approval list.

    setChatFileApprovals((current) => [
      ...current.filter(
        (item) => item.id !== approval.id
      ),
      approval,
    ]);

    // Step 6:
    // Update timeline links immediately.
    // Refresh will load the durable DB link.

    setApprovalMessageLinks((current) => [
      ...current.filter(
        (link) =>
          link.approval_id !== approval.id
      ),
      {
        approval_id: approval.id,
        conversation_id: conversationId,
        message_id: savedMessage.id,
      },
    ]);

    await loadConversationList();
  }

  // =====================================================
  // DETERMINISTIC + MULTILINGUAL FILE PLANNING
  // =====================================================

  async function resolveFileProposal(
    content: string,
    signal: AbortSignal
  ): Promise<FileResolution> {
    const intent =
      detectPossibleFileAction(content);

    if (!intent.possibleFileAction) {
      return {
        kind: "none",
      };
    }

    // First try deterministic planning.

    const deterministic =
      await planNaturalLanguageFileAction(
        content,
        signal
      );

    if (
      isSafeFileActionPlan(
        deterministic
      )
    ) {
      return {
        kind: "proposal",
        proposal: {
          filename:
            deterministic.filename,
          content:
            deterministic.content,
        },
      };
    }

    if (deterministic.recognized) {
      throw new Error(
        "ORVYN rejected an invalid deterministic file proposal."
      );
    }

    // Structured multilingual AI planning.

    const multilingual =
      await planMultilingualFileAction(
        content,
        signal
      );

    if (
      isValidMultilingualFileProposal(
        multilingual
      )
    ) {
      return {
        kind: "proposal",
        proposal: {
          filename:
            multilingual.filename,
          content:
            multilingual.content,
        },
      };
    }

    if (
      multilingual.action ===
      "needs_clarification"
    ) {
      return {
        kind: "clarification",
        message:
          multilingual.reason ||
          "Please specify the filename and what the file should contain.",
      };
    }

    if (
      multilingual.action === "no_action"
    ) {
      return {
        kind: "none",
      };
    }

    throw new Error(
      "ORVYN rejected an invalid multilingual file proposal."
    );
  }

  // =====================================================
  // MAIN SEND HANDLER
  // =====================================================

  async function handleSend(
    content: string,
    files: File[]
  ) {
    if (
      isLoading ||
      sendLockRef.current
    ) {
      return;
    }

    sendLockRef.current = true;

    const controller =
      new AbortController();

    abortControllerRef.current =
      controller;

    try {
      const fileCommand =
        parseChatFileCommand(content);

      // -------------------------------------------------
      // INVALID /file COMMAND
      // -------------------------------------------------

      if (
        fileCommand.kind === "invalid"
      ) {
        setError(fileCommand.error);
        return;
      }

      // -------------------------------------------------
      // EXPLICIT /file COMMAND
      // -------------------------------------------------

      if (
        fileCommand.kind === "valid"
      ) {
        if (files.length > 0) {
          setError(
            "Do not attach files to a /file command."
          );
          return;
        }

        setError(null);
        setIsLoading(true);
        setStreamStarted(true);

        try {
          await createFileApproval(
            {
              filename:
                fileCommand.payload.filename,
              content:
                fileCommand.payload.content,
            },
            content
          );
        } catch (err) {
          setError(
            getErrorMessage(
              err,
              "Unable to create approval request."
            )
          );
        } finally {
          setIsLoading(false);
          setStreamStarted(false);
        }

        return;
      }

      // -------------------------------------------------
      // NATURAL LANGUAGE FILE ACTION
      // -------------------------------------------------

      if (
        files.length === 0 &&
        content.trim().length > 0 &&
        content.length <= 8192 &&
        detectPossibleFileAction(content)
          .possibleFileAction
      ) {
        setError(null);
        setIsLoading(true);
        setStreamStarted(false);

        try {
          const result =
            await resolveFileProposal(
              content,
              controller.signal
            );

          if (
            controller.signal.aborted
          ) {
            return;
          }

          if (
            result.kind === "proposal"
          ) {
            setStreamStarted(true);

            await createFileApproval(
              result.proposal,
              content
            );

            return;
          }

          if (
            result.kind === "clarification"
          ) {
            setError(result.message);
            return;
          }

          // "none" continues into normal chat.
        } catch (err) {
          if (
            controller.signal.aborted ||
            isAbortError(err)
          ) {
            return;
          }

          // Fail closed:
          // Never silently execute unsafe file actions.

          setError(
            getErrorMessage(
              err,
              "ORVYN could not safely plan the file action."
            )
          );

          return;
        } finally {
          setIsLoading(false);
          setStreamStarted(false);
        }
      }

      // =================================================
      // NORMAL GEMINI / RAG / ATTACHMENT CHAT
      // =================================================

      const temporaryUserId =
        crypto.randomUUID();

      const temporaryAssistantId =
        crypto.randomUUID();

      let realAssistantMessageId:
        string | null = null;

      let streamConversationId:
        string | null =
        activeConversationId;

      let uploadedAttachmentIds:
        string[] = [];

      let indexedDocumentIds:
        string[] = [];

      let requestAccepted = false;

      setError(null);
      setIsLoading(true);
      setStreamStarted(false);

      try {
        // -----------------------------------------------
        // UPLOAD ATTACHMENTS
        // -----------------------------------------------

        const uploadedAttachments =
          files.length > 0
            ? await uploadAttachments(files)
            : [];

        uploadedAttachmentIds =
          uploadedAttachments.map(
            (attachment) =>
              attachment.id
          );

        // -----------------------------------------------
        // INDEX RAG ATTACHMENTS
        // -----------------------------------------------

        const ragAttachments =
          uploadedAttachments.filter(
            (attachment) =>
              RAG_MIME_TYPES.has(
                attachment.mime_type
              )
          );

        if (
          ragAttachments.length > 0
        ) {
          const indexedDocuments =
            await Promise.all(
              ragAttachments.map(
                (attachment) =>
                  indexAttachment(
                    attachment.id
                  )
              )
            );

          indexedDocumentIds =
            indexedDocuments.map(
              (document) =>
                document.id
            );
        }

        // -----------------------------------------------
        // TEMPORARY USER MESSAGE
        // -----------------------------------------------

        const temporaryUserMessage:
          ChatMessage = {
            id: temporaryUserId,
            role: "user",
            content,
            status: "completed",
            attachments:
              uploadedAttachments,
            sources: [],
            web_sources: [],
          };

        // -----------------------------------------------
        // TEMPORARY ASSISTANT MESSAGE
        // -----------------------------------------------

        const temporaryAssistantMessage:
          ChatMessage = {
            id: temporaryAssistantId,
            role: "assistant",
            content: "",
            status: "pending",
            sources: [],
            web_sources: [],
          };

        setMessages((current) => [
          ...current,
          temporaryUserMessage,
          temporaryAssistantMessage,
        ]);

        // -----------------------------------------------
        // CHAT REQUEST
        // -----------------------------------------------

        const chatRequest:
          Parameters<
            typeof streamChatMessage
          >[0] & {
            web_allowed: boolean;
          } = {
            message: content,
            conversation_id:
              activeConversationId,
            attachment_ids:
              uploadedAttachmentIds,
            document_ids:
              indexedDocumentIds,
            web_allowed: webAllowed,
          };

        // -----------------------------------------------
        // STREAM GEMINI / AGENT RESPONSE
        // -----------------------------------------------

        for await (
          const event of streamChatMessage(
            chatRequest,
            controller.signal
          )
        ) {
          // =============================================
          // STREAM METADATA
          // =============================================

          if (
            event.type === "meta"
          ) {
            requestAccepted = true;

            streamConversationId =
              event.conversation_id;

            realAssistantMessageId =
              event.assistant_message_id;

            setActiveConversationId(
              event.conversation_id
            );

            setMessages((current) =>
              current.map(
                (message) => {
                  if (
                    message.id ===
                    temporaryUserId
                  ) {
                    return {
                      ...message,
                      id:
                        event.user_message_id,
                    };
                  }

                  if (
                    message.id ===
                    temporaryAssistantId
                  ) {
                    return {
                      ...message,
                      id:
                        event.assistant_message_id,
                      provider:
                        event.provider,
                      model:
                        event.model,
                      sources:
                        event.sources ?? [],
                      web_sources:
                        event.web_sources ?? [],
                    };
                  }

                  return message;
                }
              )
            );

            continue;
          }

          // =============================================
          // STREAM DELTA
          // =============================================

          if (
            event.type === "delta"
          ) {
            setStreamStarted(true);

            setMessages((current) =>
              current.map(
                (message) => {
                  const isAssistant =
                    message.id ===
                      temporaryAssistantId ||
                    (
                      realAssistantMessageId !==
                        null &&
                      message.id ===
                        realAssistantMessageId
                    );

                  if (!isAssistant) {
                    return message;
                  }

                  return {
                    ...message,
                    content:
                      message.content +
                      event.content,
                    status: "streaming",
                  };
                }
              )
            );

            continue;
          }

          // =============================================
          // STREAM COMPLETE
          // =============================================

          if (
            event.type === "done"
          ) {
            streamConversationId =
              event.conversation_id;

            realAssistantMessageId =
              event.assistant_message_id;

            setActiveConversationId(
              event.conversation_id
            );

            setMessages((current) =>
              current.map(
                (message) => {
                  const isAssistant =
                    message.id ===
                      temporaryAssistantId ||
                    message.id ===
                      event.assistant_message_id;

                  if (!isAssistant) {
                    return message;
                  }

                  return {
                    ...message,
                    id:
                      event.assistant_message_id,
                    provider:
                      event.provider,
                    model:
                      event.model,
                    status: "completed",
                    sources:
                      event.sources ?? [],
                    web_sources:
                      event.web_sources ?? [],
                  };
                }
              )
            );

            continue;
          }

          // =============================================
          // STREAM ERROR
          // =============================================

          if (
            event.type === "error"
          ) {
            throw new Error(
              event.message
            );
          }
        }

        // -----------------------------------------------
        // REFRESH CONVERSATION SIDEBAR
        // -----------------------------------------------

        const updatedConversations =
          await loadConversationList();

        if (
          streamConversationId
        ) {
          const currentConversation =
            updatedConversations.find(
              (conversation) =>
                conversation.id ===
                streamConversationId
            );

          if (
            currentConversation
          ) {
            setActiveTitle(
              currentConversation.title
            );
          }
        }
      } catch (err) {
        const wasAborted =
          controller.signal.aborted ||
          isAbortError(err);

        // -----------------------------------------------
        // CLEANUP IF BACKEND DID NOT ACCEPT REQUEST
        // -----------------------------------------------

        if (
          !requestAccepted
        ) {
          for (
            const documentId of
            indexedDocumentIds
          ) {
            try {
              await deleteDocument(
                documentId
              );
            } catch {
              // Best-effort cleanup.
            }
          }

          for (
            const attachmentId of
            uploadedAttachmentIds
          ) {
            try {
              await deleteAttachment(
                attachmentId
              );
            } catch {
              // Best-effort cleanup.
            }
          }
        }

        if (
          !wasAborted
        ) {
          setError(
            getErrorMessage(
              err,
              "Unable to get a response from ORVYN."
            )
          );
        }

        // -----------------------------------------------
        // MARK FAILED / CANCELLED ASSISTANT MESSAGE
        // -----------------------------------------------

        setMessages((current) =>
          current
            .map((message) => {
              const isAssistant =
                message.id ===
                  temporaryAssistantId ||
                (
                  realAssistantMessageId !==
                    null &&
                  message.id ===
                    realAssistantMessageId
                );

              if (
                !isAssistant
              ) {
                return message;
              }

              return {
                ...message,
                status: wasAborted
                  ? ("cancelled" as const)
                  : ("failed" as const),
              };
            })
            .filter(
              (message) =>
                !(
                  (
                    message.id ===
                      temporaryAssistantId ||
                    message.id ===
                      realAssistantMessageId
                  ) &&
                  message.content.length === 0
                )
            )
        );
      } finally {
        setIsLoading(false);
        setStreamStarted(false);
      }
    } finally {
      if (
        abortControllerRef.current ===
        controller
      ) {
        abortControllerRef.current =
          null;
      }

      sendLockRef.current = false;
    }
  }

  // =====================================================
  // STOP GENERATING
  // =====================================================

  function handleStopGenerating() {
    abortControllerRef.current?.abort();
  }

  // =====================================================
  // NEW CHAT
  // =====================================================

  function handleNewChat() {
    if (
      isLoading
    ) {
      return;
    }

    resetChatView();
  }

  // =====================================================
  // OPEN CONVERSATION + DURABLE TIMELINE
  // =====================================================

  async function handleOpenConversation(
    conversationId: string
  ) {
    if (
      isLoading
    ) {
      return;
    }

    const loadId =
      ++conversationLoadRef.current;

    setError(null);
    setIsLoading(true);

    try {
      // Fetch conversation, approvals and
      // exact message-to-approval links together.

      const [
        conversation,
        approvalHistory,
        messageLinks,
      ] = await Promise.all([
        getConversation(
          conversationId
        ),
        getConversationToolApprovals(
          conversationId
        ),
        getConversationApprovalMessageLinks(
          conversationId
        ),
      ]);

      // Ignore stale responses if the user
      // switched conversations meanwhile.

      if (
        loadId !==
        conversationLoadRef.current
      ) {
        return;
      }

      setActiveConversationId(
        conversation.id
      );

      setActiveTitle(
        conversation.title
      );

      // -----------------------------------------------
      // RESTORE CHAT MESSAGES
      // -----------------------------------------------

      const loadedMessages:
        ChatMessage[] =
        conversation.messages.map(
          (message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            provider:
              message.provider ??
              undefined,
            model:
              message.model ??
              undefined,
            status: message.status,
            attachments:
              message.attachments,
            sources:
              message.sources ?? [],
            web_sources:
              message.web_sources ?? [],
          })
        );

      setMessages(
        loadedMessages.length > 0
          ? loadedMessages
          : [INITIAL_MESSAGE]
      );

      // -----------------------------------------------
      // RESTORE APPROVAL HISTORY
      // -----------------------------------------------

      setChatFileApprovals(
        approvalHistory.items
      );

      // -----------------------------------------------
      // RESTORE EXACT MESSAGE LINKS
      // -----------------------------------------------

      setApprovalMessageLinks(
        messageLinks.items
      );

      setSidebarOpen(false);
    } catch (err) {
      if (
        loadId ===
        conversationLoadRef.current
      ) {
        setError(
          getErrorMessage(
            err,
            "Unable to open conversation."
          )
        );
      }
    } finally {
      if (
        loadId ===
        conversationLoadRef.current
      ) {
        setIsLoading(false);
      }
    }
  }

  // =====================================================
  // RENAME CONVERSATION
  // =====================================================

  async function handleRenameConversation(
    conversationId: string,
    currentTitle: string
  ) {
    if (
      isLoading
    ) {
      return;
    }

    const newTitle =
      window.prompt(
        "Rename conversation",
        currentTitle
      );

    if (
      !newTitle
    ) {
      return;
    }

    const cleanedTitle =
      newTitle.trim();

    if (
      !cleanedTitle ||
      cleanedTitle === currentTitle
    ) {
      return;
    }

    try {
      await renameConversation(
        conversationId,
        cleanedTitle
      );

      if (
        activeConversationId ===
        conversationId
      ) {
        setActiveTitle(
          cleanedTitle
        );
      }

      await loadConversationList();
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          "Unable to rename conversation."
        )
      );
    }
  }

  // =====================================================
  // DELETE CONVERSATION
  // =====================================================

  async function handleDeleteConversation(
    conversationId: string
  ) {
    if (
      isLoading
    ) {
      return;
    }

    if (
      !window.confirm(
        "Are you sure you want to delete this conversation?"
      )
    ) {
      return;
    }

    try {
      await deleteConversation(
        conversationId
      );

      if (
        activeConversationId ===
        conversationId
      ) {
        resetChatView();
      }

      await loadConversationList();
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          "Unable to delete conversation."
        )
      );
    }
  }

  // =====================================================
  // VOICE ERROR
  // =====================================================

  function handleVoiceError(
    message: string
  ) {
    setError(message);
  }

  // =====================================================
  // LOGOUT
  // =====================================================

  async function handleLogout() {
    try {
      await logout();
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          "Unable to sign out."
        )
      );
    }
  }

  // =====================================================
  // CHAT UI
  // =====================================================

  return (
    <div className="flex h-screen bg-gray-950 text-white">
      {/* MOBILE SIDEBAR OVERLAY */}

      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() =>
            setSidebarOpen(false)
          }
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
        />
      )}

      {/* ============================================= */}
      {/* SIDEBAR */}
      {/* ============================================= */}

      <aside
        className={`
          fixed inset-y-0 left-0 z-40
          flex w-72 shrink-0 flex-col
          border-r border-gray-800 bg-gray-950
          transition-transform duration-200
          md:static md:z-auto md:translate-x-0
          ${
            sidebarOpen
              ? "translate-x-0"
              : "-translate-x-full"
          }
        `}
      >
        <div className="p-4">
          <div className="mb-3 flex items-center justify-between md:hidden">
            <span className="font-semibold text-white">
              ORVYN
            </span>

            <button
              type="button"
              onClick={() =>
                setSidebarOpen(false)
              }
              className="rounded-lg px-2 py-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              aria-label="Close sidebar"
            >
              ×
            </button>
          </div>

          <button
            type="button"
            onClick={handleNewChat}
            disabled={isLoading}
            className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-left text-sm font-medium transition hover:bg-gray-800 disabled:opacity-50"
          >
            + New Chat
          </button>

          <Link
            href="/agent-executions"
            onClick={() =>
              setSidebarOpen(false)
            }
            className="mt-3 flex w-full items-center gap-3 rounded-xl border border-gray-800 px-4 py-3 text-sm font-medium text-gray-300 transition hover:border-gray-600 hover:bg-gray-900 hover:text-white"
          >
            <span aria-hidden="true">
              ◷
            </span>

            <span>
              Agent History
            </span>
          </Link>

          <Link
            href="/tool-approvals"
            onClick={() =>
              setSidebarOpen(false)
            }
            className="mt-3 flex w-full items-center gap-3 rounded-xl border border-gray-800 px-4 py-3 text-sm font-medium text-gray-300 transition hover:border-gray-600 hover:bg-gray-900 hover:text-white"
          >
            <span aria-hidden="true">
              ✓
            </span>

            <span>
              Tool Approvals
            </span>
          </Link>
        </div>

        {/* =========================================== */}
        {/* CONVERSATIONS */}
        {/* =========================================== */}

        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-gray-500">
            Conversations
          </p>

          {sidebarLoading && (
            <p className="px-2 py-3 text-sm text-gray-500">
              Loading chats...
            </p>
          )}

          {!sidebarLoading &&
            conversations.length === 0 && (
              <p className="px-2 py-3 text-sm text-gray-500">
                No conversations yet.
              </p>
            )}

          <div className="space-y-1">
            {conversations.map(
              (conversation) => (
                <div
                  key={conversation.id}
                  className={`
                    group flex items-center rounded-lg
                    ${
                      activeConversationId ===
                      conversation.id
                        ? "bg-gray-800"
                        : "hover:bg-gray-900"
                    }
                  `}
                >
                  <button
                    type="button"
                    disabled={isLoading}
                    onClick={() =>
                      void handleOpenConversation(
                        conversation.id
                      )
                    }
                    className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm text-gray-300 disabled:opacity-50"
                    title={
                      conversation.title
                    }
                  >
                    {
                      conversation.title
                    }
                  </button>

                  <div className="flex items-center opacity-0 transition group-hover:opacity-100">
                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() =>
                        void handleRenameConversation(
                          conversation.id,
                          conversation.title
                        )
                      }
                      className="px-2 py-2 text-sm text-gray-500 transition hover:text-blue-400 disabled:opacity-50"
                      aria-label="Rename conversation"
                      title="Rename"
                    >
                      ✎
                    </button>

                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() =>
                        void handleDeleteConversation(
                          conversation.id
                        )
                      }
                      className="px-2 py-2 text-sm text-gray-500 transition hover:text-red-400 disabled:opacity-50"
                      aria-label="Delete conversation"
                      title="Delete"
                    >
                      ×
                    </button>
                  </div>
                </div>
              )
            )}
          </div>
        </div>

        {/* =========================================== */}
        {/* USER / LOGOUT */}
        {/* =========================================== */}

        <div className="border-t border-gray-800 p-4">
          <p className="truncate text-xs text-gray-500">
            {user?.email}
          </p>

          <button
            type="button"
            onClick={() =>
              void handleLogout()
            }
            className="mt-3 text-sm text-gray-400 transition hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ============================================= */}
      {/* MAIN CHAT */}
      {/* ============================================= */}

      <section className="flex min-w-0 flex-1 flex-col bg-gray-50 text-gray-900">
        {/* =========================================== */}
        {/* HEADER */}
        {/* =========================================== */}

        <header className="border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
          <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() =>
                  setSidebarOpen(true)
                }
                className="shrink-0 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-50 md:hidden"
                aria-label="Open sidebar"
              >
                ☰
              </button>

              <div className="min-w-0">
                <h1 className="text-xl font-bold tracking-tight">
                  ORVYN
                </h1>

                <p className="truncate text-sm text-gray-500">
                  {activeTitle}
                </p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <button
                type="button"
                onClick={() =>
                  setWebAllowed(
                    (current) =>
                      !current
                  )
                }
                disabled={isLoading}
                aria-pressed={
                  webAllowed
                }
                title={
                  webAllowed
                    ? "Public web access is enabled"
                    : "Public web access is disabled"
                }
                className={`
                  flex items-center gap-2 rounded-full
                  border px-3 py-2 text-xs font-medium
                  transition
                  ${
                    webAllowed
                      ? "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                      : "border-gray-200 bg-gray-100 text-gray-500 hover:bg-gray-200"
                  }
                  ${
                    isLoading
                      ? "cursor-not-allowed opacity-60"
                      : ""
                  }
                `}
              >
                <span>
                  🌐
                </span>

                <span className="hidden sm:inline">
                  Web
                </span>

                <span>
                  {webAllowed
                    ? "ON"
                    : "OFF"}
                </span>
              </button>

              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className="h-2 w-2 rounded-full bg-green-500" />

                <span className="hidden sm:inline">
                  AI Online
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* =========================================== */}
        {/* UNIFIED AGENT TIMELINE */}
        {/* =========================================== */}

        <main className="flex-1 overflow-y-auto px-3 py-5 sm:px-4 sm:py-6">
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
            <UnifiedAgentTimeline
              messages={messages}
              approvals={chatFileApprovals}
              approvalLinks={approvalMessageLinks}
            />

            {/* ======================================= */}
            {/* THINKING INDICATOR */}
            {/* ======================================= */}

            {isLoading &&
              !streamStarted && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500 shadow-sm">
                    ORVYN is thinking...
                  </div>
                </div>
              )}

            {/* ======================================= */}
            {/* ERROR MESSAGE */}
            {/* ======================================= */}

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </main>

        {/* =========================================== */}
        {/* COMPOSER: TEXT / FILES / VOICE */}
        {/* =========================================== */}

        <ChatComposer
          onSend={handleSend}
          onStop={handleStopGenerating}
          onVoiceError={
            handleVoiceError
          }
          disabled={false}
          isGenerating={
            isLoading
          }
        />
      </section>
    </div>
  );
}
