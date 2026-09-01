"use client";

import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useState,
} from "react";

import {
  useSpeechRecognition,
} from "@/hooks/useSpeechRecognition";


interface ChatComposerProps {
  onSend: (
    message: string
  ) => Promise<void>;

  onStop?: () => void;

  onVoiceError?: (
    message: string
  ) => void;

  disabled?: boolean;

  isGenerating?: boolean;
}


export default function ChatComposer({
  onSend,
  onStop,
  onVoiceError,
  disabled = false,
  isGenerating = false,
}: ChatComposerProps) {
  const [
    message,
    setMessage,
  ] = useState("");


  const handleTranscript =
    useCallback(
      (
        transcript: string
      ) => {
        setMessage(
          (current) => {
            const cleanedCurrent =
              current.trim();


            if (
              !cleanedCurrent
            ) {
              return transcript;
            }


            return `${cleanedCurrent} ${transcript}`;
          }
        );
      },
      []
    );


  const handleVoiceError =
    useCallback(
      (
        errorMessage: string
      ) => {
        onVoiceError?.(
          errorMessage
        );
      },
      [
        onVoiceError,
      ]
    );


  const {
    isListening,
    isSupported,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    language:
      "en-IN",

    onTranscript:
      handleTranscript,

    onError:
      handleVoiceError,
  });


  async function handleSubmit(
    event:
      FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();


    if (isGenerating) {
      onStop?.();

      return;
    }


    const trimmedMessage =
      message.trim();


    if (
      !trimmedMessage ||
      disabled
    ) {
      return;
    }


    if (isListening) {
      stopListening();
    }


    setMessage("");


    await onSend(
      trimmedMessage
    );
  }


  function handleKeyDown(
    event:
      KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key ===
        "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();


      if (
        !isGenerating
      ) {
        event.currentTarget
          .form
          ?.requestSubmit();
      }
    }
  }


  function handleMicrophoneClick() {
    if (
      disabled ||
      isGenerating ||
      !isSupported
    ) {
      return;
    }


    if (isListening) {
      stopListening();

      return;
    }


    startListening();
  }


  return (
    <form
      onSubmit={
        handleSubmit
      }
      className="border-t border-gray-200 bg-white p-4"
    >
      <div className="mx-auto flex max-w-4xl items-end gap-3 rounded-2xl border border-gray-300 bg-white p-3 shadow-sm focus-within:border-gray-500">

        <button
          type="button"
          onClick={
            handleMicrophoneClick
          }
          disabled={
            disabled ||
            isGenerating ||
            !isSupported
          }
          aria-label={
            isListening
              ? "Stop voice input"
              : "Start voice input"
          }
          title={
            !isSupported
              ? "Voice input is not supported in this browser"
              : isListening
                ? "Stop listening"
                : "Speak"
          }
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-lg transition ${
            isListening
              ? "border-red-200 bg-red-50 text-red-600"
              : "border-gray-200 bg-gray-50 text-gray-700 hover:bg-gray-100"
          } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          {isListening
            ? "■"
            : "🎤"}
        </button>


        <textarea
          value={
            message
          }
          onChange={(
            event
          ) =>
            setMessage(
              event.target.value
            )
          }
          onKeyDown={
            handleKeyDown
          }
          placeholder={
            isGenerating
              ? "ORVYN is responding..."
              : isListening
                ? "Listening..."
                : "Message ORVYN..."
          }
          rows={1}
          disabled={
            disabled ||
            isGenerating
          }
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed"
        />


        <button
          type="submit"
          disabled={
            !isGenerating &&
            (
              disabled ||
              !message.trim()
            )
          }
          className={`rounded-xl px-5 py-3 text-sm font-medium text-white transition ${
            isGenerating
              ? "bg-red-600 hover:bg-red-700"
              : "bg-gray-900 hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          }`}
        >
          {isGenerating
            ? "Stop"
            : "Send"}
        </button>

      </div>


      <p className="mx-auto mt-2 max-w-4xl text-center text-xs text-gray-400">
        {isGenerating
          ? "Stop to cancel the current response"
          : isListening
            ? "Listening… speak now"
            : !isSupported
              ? "Voice input is not supported in this browser"
              : "Enter to send · Shift + Enter for a new line · Mic for voice"}
      </p>

    </form>
  );
}