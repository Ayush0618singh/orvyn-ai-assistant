"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import ChatComposer from "@/components/chat/ChatComposer";
import MessageBubble from "@/components/chat/MessageBubble";
import { sendChatMessage } from "@/services/api";
import type { ApiChatMessage } from "@/types/api";
import type { ChatMessage } from "@/types/chat";


const WELCOME_MESSAGE_ID =
  "orvyn-welcome";


const INITIAL_MESSAGE: ChatMessage = {
  id: WELCOME_MESSAGE_ID,
  role: "assistant",
  content:
    "Hello! Main ORVYN hoon. Aap mujhse English, Hindi ya Hinglish me baat kar sakte hain.",
};


export default function ChatInterface() {
  const [messages, setMessages] =
    useState<ChatMessage[]>([
      INITIAL_MESSAGE,
    ]);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const bottomRef =
    useRef<HTMLDivElement | null>(
      null
    );


  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading]);


  async function handleSend(
    content: string
  ): Promise<void> {
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
    };

    const updatedMessages = [
      ...messages,
      userMessage,
    ];

    setMessages(updatedMessages);

    setError(null);
    setIsLoading(true);

    try {
      const conversationForApi: ApiChatMessage[] =
        updatedMessages
          .filter(
            (message) =>
              message.id !==
              WELCOME_MESSAGE_ID
          )
          .map((message) => ({
            role: message.role,
            content: message.content,
          }));

      const result =
        await sendChatMessage({
          messages:
            conversationForApi,
        });

      const assistantMessage: ChatMessage =
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.response,
          model: result.model,
          provider: result.provider,
        };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to get a response from ORVYN."
      );
    } finally {
      setIsLoading(false);
    }
  }


  function handleNewChat() {
    if (isLoading) {
      return;
    }

    setMessages([
      INITIAL_MESSAGE,
    ]);

    setError(null);
  }


  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              ORVYN
            </h1>

            <p className="text-xs text-gray-500">
              Personal Multilingual
              Agentic AI Assistant
            </p>
          </div>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handleNewChat}
              disabled={isLoading}
              className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              New Chat
            </button>

            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              AI Online
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-5">
          {messages.map(
            (message) => (
              <MessageBubble
                key={message.id}
                message={message}
              />
            )
          )}

          {isLoading && (
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

          <div ref={bottomRef} />
        </div>
      </main>

      <ChatComposer
        onSend={handleSend}
        disabled={isLoading}
      />
    </div>
  );
}