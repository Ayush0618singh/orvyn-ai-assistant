"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  useSpeechSynthesis,
} from "@/hooks/useSpeechSynthesis";

import type {
  ChatMessage,
} from "@/types/chat";


interface MessageBubbleProps {
  message: ChatMessage;
}


const VOICE_STORAGE_KEY =
  "orvyn_preferred_voice";


function cleanTextForSpeech(
  text: string
) {
  return text
    .replace(
      /```[\s\S]*?```/g,
      " Code block omitted. "
    )
    .replace(
      /`([^`]+)`/g,
      "$1"
    )
    .replace(
      /\*\*([^*]+)\*\*/g,
      "$1"
    )
    .replace(
      /\*([^*]+)\*/g,
      "$1"
    )
    .replace(
      /__([^_]+)__/g,
      "$1"
    )
    .replace(
      /_([^_]+)_/g,
      "$1"
    )
    .replace(
      /^#{1,6}\s+/gm,
      ""
    )
    .replace(
      /^\s*[-*+]\s+/gm,
      ""
    )
    .replace(
      /^\s*\d+\.\s+/gm,
      ""
    )
    .replace(
      /\[([^\]]+)\]\([^)]+\)/g,
      "$1"
    )
    .replace(
      /https?:\/\/\S+/g,
      " link "
    )
    .replace(
      /[*_#>`~]/g,
      ""
    )
    .replace(
      /\s+/g,
      " "
    )
    .trim();
}


function detectSpeechLanguage(
  text: string
) {
  const hasHindi =
    /[\u0900-\u097F]/.test(
      text
    );

  return hasHindi
    ? "hi-IN"
    : "en-IN";
}


function getStoredVoice() {
  if (
    typeof window ===
    "undefined"
  ) {
    return "";
  }

  return (
    window.localStorage.getItem(
      VOICE_STORAGE_KEY
    ) ?? ""
  );
}


export default function MessageBubble({
  message,
}: MessageBubbleProps) {
  const isUser =
    message.role ===
    "user";

  const isCancelled =
    message.status ===
    "cancelled";

  const isFailed =
    message.status ===
    "failed";


  const [
    selectedVoice,
    setSelectedVoice,
  ] = useState<string>(
    getStoredVoice
  );


  const {
    speak,
    stopSpeaking,
    isSpeaking,
    isSupported,
    voices,
  } = useSpeechSynthesis();


  const speechLanguage =
    detectSpeechLanguage(
      message.content
    );


  const relevantVoices =
    useMemo(() => {
      const prefix =
        speechLanguage
          .split("-")[0]
          .toLowerCase();

      return voices.filter(
        (voice) =>
          voice.lang
            .toLowerCase()
            .startsWith(
              prefix
            )
      );
    }, [
      voices,
      speechLanguage,
    ]);


  function handleVoiceChange(
    voiceName: string
  ) {
    setSelectedVoice(
      voiceName
    );

    if (
      typeof window ===
      "undefined"
    ) {
      return;
    }


    if (voiceName) {
      window.localStorage.setItem(
        VOICE_STORAGE_KEY,
        voiceName
      );
    } else {
      window.localStorage.removeItem(
        VOICE_STORAGE_KEY
      );
    }
  }


  function handleSpeech() {
    if (isSpeaking) {
      stopSpeaking();

      return;
    }


    const cleanedText =
      cleanTextForSpeech(
        message.content
      );


    if (!cleanedText) {
      return;
    }


    speak(
      cleanedText,
      {
        language:
          speechLanguage,

        voiceName:
          selectedVoice ||
          undefined,

        rate:
          0.95,

        pitch:
          1,

        volume:
          1,
      }
    );
  }


  return (
    <div
      className={`flex w-full ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm md:max-w-[75%] ${
          isUser
            ? "bg-gray-900 text-white"
            : "border border-gray-200 bg-white text-gray-800"
        }`}
      >
        {message.content && (
          <p className="whitespace-pre-wrap">
            {message.content}
          </p>
        )}


        {!isUser &&
          isCancelled && (
            <p
              className={`text-xs text-gray-400 ${
                message.content
                  ? "mt-3 border-t border-gray-100 pt-2"
                  : ""
              }`}
            >
              Response stopped
            </p>
          )}


        {!isUser &&
          isFailed && (
            <p
              className={`text-xs text-red-500 ${
                message.content
                  ? "mt-3 border-t border-gray-100 pt-2"
                  : ""
              }`}
            >
              Response generation failed
            </p>
          )}


        {!isUser &&
          message.content &&
          message.status ===
            "completed" && (
            <div className="mt-3 border-t border-gray-100 pt-2">

              <div className="flex flex-wrap items-center gap-2">

                <button
                  type="button"
                  onClick={
                    handleSpeech
                  }
                  disabled={
                    !isSupported
                  }
                  className="rounded-lg px-2 py-1 text-xs text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40"
                  title={
                    isSpeaking
                      ? "Stop speaking"
                      : "Read response aloud"
                  }
                  aria-label={
                    isSpeaking
                      ? "Stop speaking"
                      : "Read response aloud"
                  }
                >
                  {isSpeaking
                    ? "⏹ Stop"
                    : "🔊 Speak"}
                </button>


                {isSupported &&
                  relevantVoices.length >
                    0 && (
                    <select
                      value={
                        selectedVoice
                      }
                      onChange={(
                        event
                      ) =>
                        handleVoiceChange(
                          event.target.value
                        )
                      }
                      className="max-w-48 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-500 outline-none"
                      aria-label="Select speech voice"
                      title="Select voice"
                    >
                      <option value="">
                        Auto Voice
                      </option>

                      {relevantVoices.map(
                        (voice) => (
                          <option
                            key={`${voice.name}-${voice.lang}`}
                            value={
                              voice.name
                            }
                          >
                            {voice.name}
                          </option>
                        )
                      )}

                    </select>
                  )}


                {(message.model ||
                  message.provider) && (
                  <div className="text-xs text-gray-400">

                    {message.provider && (
                      <span>
                        {
                          message.provider
                        }
                      </span>
                    )}


                    {message.provider &&
                      message.model && (
                        <span>
                          {" · "}
                        </span>
                      )}


                    {message.model && (
                      <span>
                        {
                          message.model
                        }
                      </span>
                    )}

                  </div>
                )}

              </div>

            </div>
          )}

      </div>
    </div>
  );
}