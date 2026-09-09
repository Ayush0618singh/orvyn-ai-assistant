"use client";

import Image from "next/image";

import {
  Fragment,
  useMemo,
  useState,
} from "react";

import {
  useSpeechSynthesis,
} from "@/hooks/useSpeechSynthesis";

import {
  getAttachmentUrl,
} from "@/services/attachmentService";

import type {
  ChatMessage,
} from "@/types/chat";

import type {
  WebSource,
} from "@/types/webSource";


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
      /\[W\d+\]/g,
      ""
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


function getAttachmentIcon(
  mimeType: string
) {
  if (
    mimeType.startsWith(
      "image/"
    )
  ) {
    return "🖼️";
  }

  if (
    mimeType ===
    "application/pdf"
  ) {
    return "📄";
  }

  return "📝";
}


function formatSimilarity(
  similarity: number
) {
  return Math.round(
    similarity * 100
  );
}


function formatRelevance(
  relevance: number
) {
  return Math.round(
    relevance * 100
  );
}


function getWebSourceByCitation(
  webSources: WebSource[],
  citationId: string
) {
  return webSources.find(
    (source) =>
      source.citation_id ===
      citationId
  );
}


function renderContentWithWebCitations(
  content: string,
  webSources: WebSource[]
) {
  if (
    !content ||
    webSources.length === 0
  ) {
    return content;
  }

  const parts =
    content.split(
      /(\[W\d+\])/g
    );

  return parts.map(
    (
      part,
      index
    ) => {
      const match =
        part.match(
          /^\[(W\d+)\]$/
        );

      if (!match) {
        return (
          <Fragment
            key={
              `text-${index}`
            }
          >
            {part}
          </Fragment>
        );
      }

      const citationId =
        match[1];

      const source =
        getWebSourceByCitation(
          webSources,
          citationId
        );

      if (!source) {
        return (
          <Fragment
            key={
              `citation-${citationId}-${index}`
            }
          >
            {part}
          </Fragment>
        );
      }

      return (
        <a
          key={
            `citation-${citationId}-${index}`
          }
          href={
            source.url
          }
          target="_blank"
          rel="noopener noreferrer"
          title={
            source.title
          }
          className="mx-0.5 inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[11px] font-semibold leading-none text-blue-700 transition hover:border-blue-300 hover:bg-blue-100"
        >
          {citationId}
        </a>
      );
    }
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


  const [
    sourcesOpen,
    setSourcesOpen,
  ] = useState(
    false
  );


  const [
    webSourcesOpen,
    setWebSourcesOpen,
  ] = useState(
    false
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


  const webSources =
    message.web_sources ?? [];


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

      return;
    }

    window.localStorage.removeItem(
      VOICE_STORAGE_KEY
    );
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
            ? (
              "bg-gray-900 text-white"
            )
            : (
              "border border-gray-200 bg-white text-gray-800"
            )
        }`}
      >

        {message.attachments &&
          message.attachments.length >
            0 && (
            <div className="mb-3 flex flex-wrap gap-2">

              {message.attachments.map(
                (
                  attachment
                ) => (
                  <a
                    key={
                      attachment.id
                    }
                    href={
                      getAttachmentUrl(
                        attachment.id
                      )
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block max-w-64 overflow-hidden rounded-xl border transition ${
                      isUser
                        ? (
                          "border-gray-700 bg-gray-800 hover:bg-gray-700"
                        )
                        : (
                          "border-gray-200 bg-gray-50 hover:bg-gray-100"
                        )
                    }`}
                  >
                    {attachment.mime_type.startsWith(
                      "image/"
                    ) ? (
                      <div className="relative h-48 w-64">
                        <Image
                          src={
                            getAttachmentUrl(
                              attachment.id
                            )
                          }
                          alt={
                            attachment.original_name
                          }
                          fill
                          unoptimized
                          sizes="256px"
                          className="object-cover"
                        />
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 px-3 py-3">

                        <span>
                          {getAttachmentIcon(
                            attachment.mime_type
                          )}
                        </span>

                        <span
                          className={`truncate text-xs ${
                            isUser
                              ? "text-gray-200"
                              : "text-gray-700"
                          }`}
                        >
                          {
                            attachment.original_name
                          }
                        </span>

                      </div>
                    )}
                  </a>
                )
              )}

            </div>
          )}


        {message.content && (
          <p className="whitespace-pre-wrap">
            {!isUser &&
            webSources.length >
              0
              ? renderContentWithWebCitations(
                  message.content,
                  webSources
                )
              : message.content}
          </p>
        )}


        {!isUser &&
          message.sources &&
          message.sources.length >
            0 && (
            <div className="mt-4 border-t border-gray-100 pt-3">

              <button
                type="button"
                onClick={() =>
                  setSourcesOpen(
                    (current) =>
                      !current
                  )
                }
                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left text-xs font-medium text-gray-600 transition hover:bg-gray-50"
                aria-expanded={
                  sourcesOpen
                }
              >
                <span>
                  📚 Document Sources (
                  {
                    message.sources.length
                  }
                  )
                </span>

                <span className="text-gray-400">
                  {sourcesOpen
                    ? "▲"
                    : "▼"}
                </span>
              </button>


              {sourcesOpen && (
                <div className="mt-2 space-y-2">

                  {message.sources.map(
                    (
                      source,
                      index
                    ) => (
                      <div
                        key={
                          `${source.chunk_id}-${index}`
                        }
                        className="rounded-xl border border-gray-200 bg-gray-50 p-3"
                      >

                        <div className="flex flex-wrap items-center justify-between gap-2">

                          <p className="min-w-0 truncate text-xs font-semibold text-gray-800">
                            [
                            Source{" "}
                            {index + 1}
                            ]{" "}
                            {
                              source.document_name
                            }
                          </p>

                          <span className="shrink-0 text-[11px] text-gray-400">
                            Match{" "}
                            {formatSimilarity(
                              source.similarity
                            )}
                            %
                          </span>

                        </div>


                        <p className="mt-1 text-[11px] text-gray-400">
                          Chunk{" "}
                          {
                            source.chunk_index +
                            1
                          }
                        </p>


                        <p className="mt-2 max-h-36 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-gray-600">
                          {
                            source.content
                          }
                        </p>

                      </div>
                    )
                  )}

                </div>
              )}

            </div>
          )}


        {!isUser &&
          webSources.length >
            0 && (
            <div className="mt-4 border-t border-gray-100 pt-3">

              <button
                type="button"
                onClick={() =>
                  setWebSourcesOpen(
                    (current) =>
                      !current
                  )
                }
                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left text-xs font-medium text-gray-600 transition hover:bg-gray-50"
                aria-expanded={
                  webSourcesOpen
                }
              >
                <span className="flex items-center gap-1.5">
                  <span>
                    🌐
                  </span>

                  <span>
                    Web Sources (
                    {
                      webSources.length
                    }
                    )
                  </span>
                </span>

                <span className="text-gray-400">
                  {webSourcesOpen
                    ? "▲"
                    : "▼"}
                </span>
              </button>


              {webSourcesOpen && (
                <div className="mt-2 space-y-2">

                  {webSources.map(
                    (
                      source
                    ) => (
                      <a
                        key={
                          `${source.citation_id}-${source.url}`
                        }
                        href={
                          source.url
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block rounded-xl border border-gray-200 bg-gray-50 p-3 transition hover:border-blue-200 hover:bg-blue-50/40"
                      >

                        <div className="flex items-start justify-between gap-3">

                          <div className="min-w-0 flex-1">

                            <div className="flex flex-wrap items-center gap-2">

                              <span className="rounded-md border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-blue-700">
                                {
                                  source.citation_id
                                }
                              </span>

                              <span className="truncate text-[11px] text-gray-400">
                                {
                                  source.domain
                                }
                              </span>

                            </div>


                            <p className="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-gray-800">
                              {
                                source.title
                              }
                            </p>

                          </div>


                          <span
                            className="shrink-0 text-[11px] text-gray-400"
                            title="Search relevance score"
                          >
                            Match{" "}
                            {formatRelevance(
                              source.relevance_score
                            )}
                            %
                          </span>

                        </div>


                        {source.content && (
                          <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-[11px] leading-5 text-gray-500">
                            {
                              source.content
                            }
                          </p>
                        )}


                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-gray-400">

                          <span>
                            {
                              source.search_provider
                            }
                          </span>

                          <span>
                            Open source ↗
                          </span>

                        </div>

                      </a>
                    )
                  )}

                </div>
              )}

            </div>
          )}


        {!isUser &&
          isCancelled && (
            <p
              className={`text-xs text-gray-400 ${
                message.content
                  ? (
                    "mt-3 border-t border-gray-100 pt-2"
                  )
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
                  ? (
                    "mt-3 border-t border-gray-100 pt-2"
                  )
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
                        (
                          voice
                        ) => (
                          <option
                            key={
                              `${voice.name}-${voice.lang}`
                            }
                            value={
                              voice.name
                            }
                          >
                            {
                              voice.name
                            }
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