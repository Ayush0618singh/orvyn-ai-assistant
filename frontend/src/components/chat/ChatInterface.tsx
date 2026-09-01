"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import ChatComposer from "@/components/chat/ChatComposer";
import MessageBubble from "@/components/chat/MessageBubble";

import { useAuth } from "@/contexts/AuthContext";

import {
  streamChatMessage,
} from "@/services/api";

import {
  deleteConversation,
  getConversation,
  getConversations,
  renameConversation,
} from "@/services/conversationService";

import {
  deleteAttachment,
  uploadAttachments,
} from "@/services/attachmentService";

import type {
  ChatMessage,
} from "@/types/chat";

import type {
  ConversationSummary,
} from "@/types/conversation";


const INITIAL_MESSAGE: ChatMessage = {
  id: "orvyn-welcome",
  role: "assistant",
  content:
    "Hello! Main ORVYN hoon. Aap mujhse English, Hindi ya Hinglish me baat kar sakte hain.",
  status: "completed",
};


export default function ChatInterface() {
  const {
    user,
    logout,
  } = useAuth();


  const [
    messages,
    setMessages,
  ] = useState<ChatMessage[]>([
    INITIAL_MESSAGE,
  ]);


  const [
    conversations,
    setConversations,
  ] = useState<
    ConversationSummary[]
  >([]);


  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState<string | null>(
    null
  );


  const [
    activeTitle,
    setActiveTitle,
  ] = useState(
    "New Chat"
  );


  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(
    false
  );


  const [
    isLoading,
    setIsLoading,
  ] = useState(
    false
  );


  const [
    streamStarted,
    setStreamStarted,
  ] = useState(
    false
  );


  const [
    sidebarLoading,
    setSidebarLoading,
  ] = useState(
    true
  );


  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  const bottomRef =
    useRef<HTMLDivElement | null>(
      null
    );


  const abortControllerRef =
    useRef<AbortController | null>(
      null
    );


  async function loadConversationList() {
    try {
      const data =
        await getConversations();

      setConversations(
        data
      );

      return data;
    } catch (err) {
      console.error(
        "Failed to load conversations:",
        err
      );

      return [];
    } finally {
      setSidebarLoading(
        false
      );
    }
  }


  useEffect(() => {
    let cancelled =
      false;


    getConversations()
      .then((data) => {
        if (!cancelled) {
          setConversations(
            data
          );
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
          setSidebarLoading(
            false
          );
        }
      });


    return () => {
      cancelled =
        true;
    };
  }, []);


  useEffect(() => {
    bottomRef.current?.scrollIntoView(
      {
        behavior: "smooth",
      }
    );
  }, [
    messages,
    isLoading,
  ]);


  async function handleSend(
  content: string,
  files: File[]
) {
  if (isLoading) {
    return;
  }


  const controller =
    new AbortController();


  abortControllerRef.current =
    controller;


  const temporaryUserId =
    crypto.randomUUID();


  const temporaryAssistantId =
    crypto.randomUUID();


  setError(
    null
  );


  setIsLoading(
    true
  );


  setStreamStarted(
    false
  );


  let uploadedAttachmentIds:
    string[] = [];


  try {
    const uploadedAttachments =
      files.length > 0
        ? await uploadAttachments(
            files
          )
        : [];


    uploadedAttachmentIds =
      uploadedAttachments.map(
        (attachment) =>
          attachment.id
      );


    const temporaryUserMessage: ChatMessage = {
      id:
        temporaryUserId,

      role:
        "user",

      content,

      status:
        "completed",

      attachments:
        uploadedAttachments,
    };


    const temporaryAssistantMessage: ChatMessage = {
      id:
        temporaryAssistantId,

      role:
        "assistant",

      content:
        "",

      status:
        "pending",
    };


    setMessages(
      (current) => [
        ...current,
        temporaryUserMessage,
        temporaryAssistantMessage,
      ]
    );


    let streamConversationId =
      activeConversationId;


    for await (
      const event
      of streamChatMessage(
        {
          message:
            content,

          conversation_id:
            activeConversationId,

          attachment_ids:
            uploadedAttachmentIds,
        },
        controller.signal
      )
    ) {
      if (
        event.type ===
        "meta"
      ) {
        streamConversationId =
          event.conversation_id;


        setActiveConversationId(
          event.conversation_id
        );


        setMessages(
          (current) =>
            current.map(
              (message) =>
                message.id ===
                temporaryUserId
                  ? {
                      ...message,

                      id:
                        event.user_message_id,
                    }
                  : message
            )
        );


        continue;
      }


      if (
        event.type ===
        "delta"
      ) {
        setStreamStarted(
          true
        );


        setMessages(
          (current) =>
            current.map(
              (message) =>
                message.id ===
                temporaryAssistantId
                  ? {
                      ...message,

                      content:
                        message.content +
                        event.content,

                      status:
                        "streaming",
                    }
                  : message
            )
        );


        continue;
      }


      if (
        event.type ===
        "done"
      ) {
        streamConversationId =
          event.conversation_id;


        setActiveConversationId(
          event.conversation_id
        );


        setMessages(
          (current) =>
            current.map(
              (message) =>
                message.id ===
                temporaryAssistantId
                  ? {
                      ...message,

                      id:
                        event.assistant_message_id,

                      provider:
                        event.provider,

                      model:
                        event.model,

                      status:
                        "completed",
                    }
                  : message
            )
        );


        continue;
      }


      if (
        event.type ===
        "error"
      ) {
        throw new Error(
          event.message
        );
      }
    }


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
      err instanceof DOMException &&
      err.name ===
        "AbortError";


    if (
      uploadedAttachmentIds.length >
      0
    ) {
      for (
        const attachmentId
        of uploadedAttachmentIds
      ) {
        try {
          await deleteAttachment(
            attachmentId
          );
        } catch {
          // The backend may already have bound
          // the attachment to the conversation.
        }
      }
    }


    if (wasAborted) {
      setMessages(
        (current) =>
          current
            .map(
              (message) =>
                message.id ===
                temporaryAssistantId
                  ? {
                      ...message,

                      status:
                        "cancelled" as const,
                    }
                  : message
            )
            .filter(
              (message) =>
                !(
                  message.id ===
                    temporaryAssistantId &&
                  message.content.length ===
                    0
                )
            )
      );

    } else {
      setError(
        err instanceof Error
          ? err.message
          : (
              "Unable to get a response from ORVYN."
            )
      );


      setMessages(
        (current) =>
          current
            .map(
              (message) =>
                message.id ===
                temporaryAssistantId
                  ? {
                      ...message,

                      status:
                        "failed" as const,
                    }
                  : message
            )
            .filter(
              (message) =>
                !(
                  message.id ===
                    temporaryAssistantId &&
                  message.content.length ===
                    0
                )
            )
      );
    }

  } finally {
    abortControllerRef.current =
      null;


    setIsLoading(
      false
    );


    setStreamStarted(
      false
    );
  }
}


  function handleStopGenerating() {
    abortControllerRef.current?.abort();
  }


  function handleNewChat() {
    if (isLoading) {
      return;
    }


    setActiveConversationId(
      null
    );


    setActiveTitle(
      "New Chat"
    );


    setMessages([
      INITIAL_MESSAGE,
    ]);


    setError(
      null
    );


    setSidebarOpen(
      false
    );
  }


  async function handleOpenConversation(
    conversationId: string
  ) {
    if (isLoading) {
      return;
    }


    try {
      setError(
        null
      );


      const conversation =
        await getConversation(
          conversationId
        );


      setActiveConversationId(
        conversation.id
      );


      setActiveTitle(
        conversation.title
      );


    const loadedMessages: ChatMessage[] =
      conversation.messages.map(
        (message) => ({
          id:
            message.id,

          role:
            message.role,

          content:
            message.content,

          provider:
            message.provider ??
            undefined,

          model:
            message.model ??
            undefined,

          status:
            message.status,

          attachments:
            message.attachments,
        })
      );


      setMessages(
        loadedMessages.length > 0
          ? loadedMessages
          : [INITIAL_MESSAGE]
      );


      setSidebarOpen(
        false
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to open conversation."
      );
    }
  }


  async function handleRenameConversation(
    conversationId: string,
    currentTitle: string
  ) {
    if (isLoading) {
      return;
    }


    const newTitle =
      window.prompt(
        "Rename conversation",
        currentTitle
      );


    if (!newTitle) {
      return;
    }


    const cleanedTitle =
      newTitle.trim();


    if (
      cleanedTitle.length === 0 ||
      cleanedTitle ===
        currentTitle
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
        err instanceof Error
          ? err.message
          : "Unable to rename conversation."
      );
    }
  }


  async function handleDeleteConversation(
    conversationId: string
  ) {
    if (isLoading) {
      return;
    }


    const confirmed =
      window.confirm(
        "Are you sure you want to delete this conversation?"
      );


    if (!confirmed) {
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
        handleNewChat();
      }


      await loadConversationList();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete conversation."
      );
    }
  }

  function handleVoiceError(
    message: string
  ) {
    setError(
      message
    );
  }


  async function handleLogout() {
    try {
      await logout();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to sign out."
      );
    }
  }


  return (
    <div className="flex h-screen bg-gray-950 text-white">

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


      <aside
        className={`
          fixed inset-y-0 left-0 z-40
          flex w-72 shrink-0 flex-col
          border-r border-gray-800
          bg-gray-950
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
            onClick={
              handleNewChat
            }
            className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-left text-sm font-medium transition hover:bg-gray-800"
          >
            + New Chat
          </button>

        </div>


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
                  key={
                    conversation.id
                  }
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
                    onClick={() =>
                      handleOpenConversation(
                        conversation.id
                      )
                    }
                    className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm text-gray-300"
                    title={
                      conversation.title
                    }
                  >
                    {conversation.title}
                  </button>


                  <div className="flex items-center opacity-0 transition group-hover:opacity-100">

                    <button
                      type="button"
                      onClick={() =>
                        handleRenameConversation(
                          conversation.id,
                          conversation.title
                        )
                      }
                      className="px-2 py-2 text-sm text-gray-500 transition hover:text-blue-400"
                      aria-label="Rename conversation"
                      title="Rename"
                    >
                      ✎
                    </button>


                    <button
                      type="button"
                      onClick={() =>
                        handleDeleteConversation(
                          conversation.id
                        )
                      }
                      className="px-2 py-2 text-sm text-gray-500 transition hover:text-red-400"
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


        <div className="border-t border-gray-800 p-4">

          <p className="truncate text-xs text-gray-500">
            {user?.email}
          </p>


          <button
            type="button"
            onClick={
              handleLogout
            }
            className="mt-3 text-sm text-gray-400 transition hover:text-white"
          >
            Sign out
          </button>

        </div>

      </aside>


      <section className="flex min-w-0 flex-1 flex-col bg-gray-50 text-gray-900">

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


            <div className="flex shrink-0 items-center gap-2 text-xs text-gray-500">

              <span className="h-2 w-2 rounded-full bg-green-500" />

              <span className="hidden sm:inline">
                AI Online
              </span>

            </div>

          </div>

        </header>


        <main className="flex-1 overflow-y-auto px-3 py-5 sm:px-4 sm:py-6">

          <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">

            {messages.map(
              (message) => (

                <MessageBubble
                  key={message.id}
                  message={message}
                />

              )
            )}


            {isLoading &&
              !streamStarted && (
                <div className="flex justify-start">

                  <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500 shadow-sm">
                    ORVYN is thinking...
                  </div>

                </div>
              )}


            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}


            <div
              ref={
                bottomRef
              }
            />

          </div>

        </main>


        <ChatComposer
          onSend={
            handleSend
          }
          onStop={
            handleStopGenerating
          }
          onVoiceError={
            handleVoiceError
          }
          disabled={
            false
          }
          isGenerating={
            isLoading
          }
        />

      </section>

    </div>
  );
}