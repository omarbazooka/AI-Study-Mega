import React, { useEffect, useRef } from "react";
import { MessageItem } from "@/types/api/sessions";
import { Citation } from "@/types/api/ai";
import { ChatMessage } from "./ChatMessage";
import { Sparkles, MessageSquare } from "lucide-react";

interface ChatViewProps {
  messages: MessageItem[];
  currentAssistantText: string;
  activeCitations: Citation[];
  isSending: boolean;
  isLoadingHistory: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  currentAssistantText,
  activeCitations,
  isSending,
  isLoadingHistory,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, currentAssistantText]);

  if (isLoadingHistory) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2.5 text-zinc-500">
        <Sparkles className="h-6 w-6 animate-pulse text-zinc-600" />
        <span className="text-xs font-semibold tracking-wide animate-pulse">
          Loading history...
        </span>
      </div>
    );
  }

  if (messages.length === 0 && !currentAssistantText && !isSending) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-500 p-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800/80 text-zinc-400">
          <MessageSquare className="h-5 w-5" />
        </div>
        <div className="max-w-xs">
          <h5 className="text-sm font-bold text-zinc-300 mb-1">
            No history found
          </h5>
          <p className="text-xs text-zinc-500 leading-relaxed font-medium">
            Start a discussion by asking a question about the document context.
          </p>
        </div>
      </div>
    );
  }

  // Render transient streaming message if active
  const streamingMsg: MessageItem | null = currentAssistantText
    ? {
        id: "streaming",
        session_id: "streaming",
        user_id: "assistant",
        role: "assistant",
        content: currentAssistantText,
        created_at: new Date().toISOString(),
      }
    : null;

  return (
    <div 
      ref={containerRef}
      className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4.5 scrollbar-hide"
    >
      {messages.map((msg) => (
        <ChatMessage key={msg.id} message={msg} />
      ))}

      {streamingMsg && (
        <ChatMessage message={streamingMsg} citations={activeCitations} />
      )}

      {isSending && !currentAssistantText && (
        <div className="flex flex-col gap-1 max-w-[85%] self-start items-start">
          <div className="px-4 py-2.5 rounded-2xl bg-zinc-900/60 border border-zinc-800 rounded-bl-none flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce delay-0" />
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce delay-150" />
            <span className="h-2 w-2 rounded-full bg-primary animate-bounce delay-300" />
          </div>
        </div>
      )}
    </div>
  );
};
