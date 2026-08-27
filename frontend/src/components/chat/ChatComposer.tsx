"use client";

import {
  FormEvent,
  KeyboardEvent,
  useState,
} from "react";

interface ChatComposerProps {
  onSend: (message: string) => Promise<void>;
  disabled?: boolean;
}

export default function ChatComposer({
  onSend,
  disabled = false,
}: ChatComposerProps) {
  const [message, setMessage] = useState("");

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || disabled) {
      return;
    }

    setMessage("");

    await onSend(trimmedMessage);
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-gray-200 bg-white p-4"
    >
      <div className="mx-auto flex max-w-4xl items-end gap-3 rounded-2xl border border-gray-300 bg-white p-3 shadow-sm focus-within:border-gray-500">
        <textarea
          value={message}
          onChange={(event) =>
            setMessage(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder="Message ORVYN..."
          rows={1}
          disabled={disabled}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed"
        />

        <button
          type="submit"
          disabled={
            disabled || !message.trim()
          }
          className="rounded-xl bg-gray-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {disabled ? "Thinking..." : "Send"}
        </button>
      </div>

      <p className="mx-auto mt-2 max-w-4xl text-center text-xs text-gray-400">
        Enter to send · Shift + Enter for a new line
      </p>
    </form>
  );
}