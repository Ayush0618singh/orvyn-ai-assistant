import type { ChatMessage } from "@/types/chat";

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({
  message,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex w-full ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm md:max-w-[75%] ${
          isUser
            ? "bg-gray-900 text-white"
            : "border border-gray-200 bg-white text-gray-800"
        }`}
      >
        <p className="whitespace-pre-wrap">
          {message.content}
        </p>

        {!isUser && (message.model || message.provider) && (
          <div className="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-400">
            {message.provider && (
              <span>{message.provider}</span>
            )}

            {message.provider && message.model && (
              <span> · </span>
            )}

            {message.model && (
              <span>{message.model}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}