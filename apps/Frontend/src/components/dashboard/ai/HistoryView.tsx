import React, { useState, useEffect } from "react";
import { sessionsService } from "@/services/sessions.service";
import { SessionResponse } from "@/types/api/sessions";
import { MessageSquare, Clock, ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface HistoryViewProps {
  documentId: string | null;
  onSelectSession: (sessionId: string) => void;
  onClose: () => void;
}

export const HistoryView: React.FC<HistoryViewProps> = ({
  documentId,
  onSelectSession,
  onClose,
}) => {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchHistory() {
      if (!documentId) return;
      setIsLoading(true);
      try {
        const data = await sessionsService.getDocumentSessions(documentId);
        setSessions(data);
      } catch (err: any) {
        toast.error(err.message || "Failed to load chat history.");
      } finally {
        setIsLoading(false);
      }
    }
    fetchHistory();
  }, [documentId]);

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4 custom-scrollbar">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-zinc-800 pb-3">
        <button
          onClick={onClose}
          className="p-1.5 rounded-full hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors cursor-pointer"
          title="Back to Chat"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex flex-col">
          <span className="text-sm font-bold text-zinc-200">Chat History</span>
          <span className="text-xs text-zinc-500 font-medium">Load previous conversation sessions</span>
        </div>
      </div>

      {/* Sessions list */}
      {isLoading ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2.5 text-zinc-500 min-h-[160px]">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="text-xs font-semibold tracking-wide">
            Retrieving past sessions...
          </span>
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-500 p-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800/80 text-zinc-400">
            <Clock className="h-5 w-5" />
          </div>
          <div className="max-w-xs">
            <h5 className="text-sm font-bold text-zinc-300 mb-1">
              No chat history
            </h5>
            <p className="text-xs text-zinc-500 leading-relaxed font-medium">
              Your previous chats for this document will be listed here.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {sessions.map((sess) => (
            <button
              key={sess.id}
              onClick={() => onSelectSession(sess.id)}
              className="flex items-start gap-3 p-3 rounded-xl border border-zinc-800/50 bg-zinc-900/10 hover:bg-zinc-900/60 hover:border-zinc-700/80 transition-all text-left w-full group cursor-pointer"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400 group-hover:text-primary transition-colors mt-0.5 shrink-0">
                <MessageSquare className="h-4 w-4" />
              </div>
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-xs font-bold text-zinc-300 group-hover:text-white transition-colors truncate">
                  {sess.title || "New Chat"}
                </span>
                <span className="text-[10px] text-zinc-500 font-medium mt-1">
                  {new Date(sess.created_at).toLocaleString(undefined, {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
