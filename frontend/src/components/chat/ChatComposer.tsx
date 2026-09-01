"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useCallback,
  useRef,
  useState,
} from "react";

import {
  useSpeechRecognition,
} from "@/hooks/useSpeechRecognition";

import type {
  PendingAttachment,
} from "@/types/attachment";


interface ChatComposerProps {
  onSend: (
    message: string,
    files: File[]
  ) => Promise<void>;

  onStop?: () => void;

  onVoiceError?: (
    message: string
  ) => void;

  disabled?: boolean;

  isGenerating?: boolean;
}


const MAX_FILES = 5;

const MAX_FILE_SIZE =
  10 * 1024 * 1024;

const ALLOWED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
  "text/plain",
]);


function formatFileSize(
  bytes: number
) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (
    bytes <
    1024 * 1024
  ) {
    return `${(
      bytes / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    bytes /
    (1024 * 1024)
  ).toFixed(1)} MB`;
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

  const [
    attachments,
    setAttachments,
  ] = useState<
    PendingAttachment[]
  >([]);

  const fileInputRef =
    useRef<HTMLInputElement | null>(
      null
    );


  const handleTranscript =
    useCallback(
      (
        transcript: string
      ) => {
        setMessage(
          (current) => {
            const cleanedCurrent =
              current.trim();

            if (!cleanedCurrent) {
              return transcript;
            }

            return (
              `${cleanedCurrent} ${transcript}`
            );
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
    language: "en-IN",

    onTranscript:
      handleTranscript,

    onError:
      handleVoiceError,
  });


  function handleFileChange(
    event:
      ChangeEvent<HTMLInputElement>
  ) {
    const selectedFiles =
      Array.from(
        event.target.files ?? []
      );

    event.target.value = "";


    if (
      selectedFiles.length === 0
    ) {
      return;
    }


    const availableSlots =
      MAX_FILES -
      attachments.length;


    if (availableSlots <= 0) {
      onVoiceError?.(
        `Maximum ${MAX_FILES} files are allowed.`
      );

      return;
    }


    const validFiles:
      PendingAttachment[] = [];


    for (
      const file
      of selectedFiles.slice(
        0,
        availableSlots
      )
    ) {
      if (
        !ALLOWED_TYPES.has(
          file.type
        )
      ) {
        onVoiceError?.(
          `${file.name}: unsupported file type.`
        );

        continue;
      }


      if (
        file.size >
        MAX_FILE_SIZE
      ) {
        onVoiceError?.(
          `${file.name}: maximum file size is 10 MB.`
        );

        continue;
      }


      validFiles.push({
        localId:
          crypto.randomUUID(),

        file,
      });
    }


    setAttachments(
      (current) => [
        ...current,
        ...validFiles,
      ]
    );
  }


  function removeFile(
    localId: string
  ) {
    setAttachments(
      (current) =>
        current.filter(
          (attachment) =>
            attachment.localId
            !== localId
        )
    );
  }


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
      (
        !trimmedMessage &&
        attachments.length === 0
      )
      ||
      disabled
    ) {
      return;
    }


    if (isListening) {
      stopListening();
    }


    const files =
      attachments.map(
        (attachment) =>
          attachment.file
      );


    setMessage("");

    setAttachments([]);


    await onSend(
      trimmedMessage,
      files
    );
  }


  function handleKeyDown(
    event:
      KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (!isGenerating) {
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
      <div className="mx-auto max-w-4xl">

        {attachments.length >
          0 && (
          <div className="mb-3 flex flex-wrap gap-2">

            {attachments.map(
              (
                attachment
              ) => (
                <div
                  key={
                    attachment.localId
                  }
                  className="flex max-w-60 items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2"
                >
                  <span className="text-base">
                    {attachment.file.type.startsWith(
                      "image/"
                    )
                      ? "🖼️"
                      : attachment.file.type ===
                          "application/pdf"
                        ? "📄"
                        : "📝"}
                  </span>


                  <div className="min-w-0 flex-1">

                    <p className="truncate text-xs font-medium text-gray-700">
                      {
                        attachment
                          .file
                          .name
                      }
                    </p>

                    <p className="text-[10px] text-gray-400">
                      {formatFileSize(
                        attachment
                          .file
                          .size
                      )}
                    </p>

                  </div>


                  <button
                    type="button"
                    onClick={() =>
                      removeFile(
                        attachment.localId
                      )
                    }
                    disabled={
                      isGenerating
                    }
                    className="text-sm text-gray-400 transition hover:text-red-500"
                    aria-label={
                      `Remove ${attachment.file.name}`
                    }
                  >
                    ×
                  </button>

                </div>
              )
            )}

          </div>
        )}


        <div className="flex items-end gap-2 rounded-2xl border border-gray-300 bg-white p-3 shadow-sm focus-within:border-gray-500">

          <input
            ref={
              fileInputRef
            }
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.webp,.pdf,.txt"
            onChange={
              handleFileChange
            }
            className="hidden"
          />


          <button
            type="button"
            onClick={() =>
              fileInputRef
                .current
                ?.click()
            }
            disabled={
              disabled ||
              isGenerating ||
              attachments.length >=
                MAX_FILES
            }
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-gray-50 text-xl text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Attach file"
            title="Attach image or document"
          >
            +
          </button>


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
                (
                  !message.trim() &&
                  attachments.length ===
                    0
                )
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


        <p className="mt-2 text-center text-xs text-gray-400">
          {isGenerating
            ? "Stop to cancel the current response"
            : isListening
              ? "Listening… speak now"
              : "Images, PDF, TXT · Max 5 files · 10 MB each"}
        </p>

      </div>
    </form>
  );
}