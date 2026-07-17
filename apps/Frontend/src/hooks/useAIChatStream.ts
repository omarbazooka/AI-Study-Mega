/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/set-state-in-effect, @typescript-eslint/no-unused-vars */
import { useState, useEffect, useRef, useCallback } from "react";
import { sessionsService } from "@/services/sessions.service";
import { aiService } from "@/services/ai.service";
import { MessageItem } from "@/types/api/sessions";
import { Citation } from "@/types/api/ai";
import { ApiError } from "@/types/api/common";
import { toast } from "sonner";
import { v4 as uuidv4 } from "uuid";

interface UseAIChatStreamProps {
  documentId: string | null;
  userId: string | null;
  documentReady: boolean;
}

export function useAIChatStream({ documentId, userId, documentReady }: UseAIChatStreamProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [streamStage, setStreamStage] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<number>(0);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [currentAssistantText, setCurrentAssistantText] = useState<string>("");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [activeNodes, setActiveNodes] = useState<Record<string, any>>({});
  const [publicRequestSummary, setPublicRequestSummary] = useState<string | null>(null);
  const [stageMetadata, setStageMetadata] = useState<Record<string, any>>({});

  const abortControllerRef = useRef<AbortController | null>(null);
  const isCreatingSession = useRef<boolean>(false);
  const typingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const getStorageKey = useCallback((docId: string, usrId: string) => {
    return `ai-study-platform:session:${usrId}:${docId}`;
  }, []);

  const cancelCurrentStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (typingTimerRef.current) {
      clearInterval(typingTimerRef.current);
      typingTimerRef.current = null;
    }
  }, []);

  const startNewChat = useCallback(async () => {
    if (!documentId) return;
    setIsLoadingHistory(true);
    setMessages([]);
    cancelCurrentStream();
    try {
      const newSessionId = uuidv4();
      setSessionId(newSessionId);
    } catch (err) {
      console.error("Failed to start new chat:", err);
      toast.error("Failed to start new chat.");
    } finally {
      setIsLoadingHistory(false);
    }
  }, [documentId, cancelCurrentStream]);

  const loadChatSession = useCallback(async (sessId: string) => {
    if (!documentId) return;
    setIsLoadingHistory(true);
    setMessages([]);
    cancelCurrentStream();
    try {
      const history = await sessionsService.getSessionMessages(documentId, sessId);
      setSessionId(sessId);
      setMessages(history.messages);
    } catch (err) {
      console.error("Failed to load chat session:", err);
      toast.error("Failed to load chat session.");
    } finally {
      setIsLoadingHistory(false);
    }
  }, [documentId, cancelCurrentStream]);

  const initializeSessionAndHistory = useCallback(async (docId: string, usrId: string) => {
    if (isCreatingSession.current) return;
    setIsLoadingHistory(true);
    setMessages([]);
    cancelCurrentStream();

    isCreatingSession.current = true;
    try {
      const newSessionId = uuidv4();
      setSessionId(newSessionId);
      isCreatingSession.current = false;
    } catch (err: any) {
      isCreatingSession.current = false;
      console.error("Session init failed:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [cancelCurrentStream]);

  // Handle document switching
  useEffect(() => {
    setSessionId(null);
    setMessages([]);
    cancelCurrentStream();
    setStreamStage(null);
    setStreamProgress(0);
    setStreamStatus(null);
    setCurrentAssistantText("");
    setActiveCitations([]);

    if (documentId && userId && documentReady) {
      initializeSessionAndHistory(documentId, userId);
    }

    return () => {
      cancelCurrentStream();
    };
  }, [documentId, userId, documentReady, initializeSessionAndHistory, cancelCurrentStream]);

  const sendMessage = async (messageText: string, language: "ar" | "en" = "ar") => {
    if (!documentId || !sessionId || !userId || isSending || !documentReady) return;

    cancelCurrentStream();
    setIsSending(true);
    setStreamStage("request_received");
    setStreamProgress(0);
    setStreamStatus("started");
    setCurrentAssistantText("");
    setActiveCitations([]);
    setCompletedStages([]);
    setActiveNodes({});
    setPublicRequestSummary(null);
    setStageMetadata({});

    // 1. Optimistic User Message update
    const userMsgId = `user-${Date.now()}`;
    const userMessage: MessageItem = {
      id: userMsgId,
      session_id: sessionId,
      user_id: userId,
      role: "user",
      content: messageText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Create AbortController for streaming request
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedText = "";
    let citationsAccumulator: Citation[] = [];

    try {
      await aiService.streamChat(
        documentId,
        {
          session_id: sessionId,
          message: messageText,
          language,
        },
        {
          onStageEvent: (event) => {
            // Keep progress monotonic
            setStreamProgress((prev) => Math.max(prev, event.progress));
            
            // Set current stage and status
            setStreamStage(event.stage);
            setStreamStatus(event.status);

            // Accumulate completed stages
            if (event.status === "completed") {
              setCompletedStages((prev) => {
                if (!prev.includes(event.stage)) {
                  return [...prev, event.stage];
                }
                return prev;
              });
            }

            // Track public request summary
            if (event.metadata?.public_request_summary) {
              setPublicRequestSummary(event.metadata.public_request_summary);
            }

            // Track stage metadata
            if (event.metadata) {
              setStageMetadata((prev) => ({ ...prev, ...event.metadata }));
            }

            // Track active task node IDs
            if (event.node_id) {
              setActiveNodes((prev) => {
                const copy = { ...prev };
                if (event.status === "started") {
                  copy[event.node_id!] = event;
                } else if (event.status === "completed" || event.status === "failed") {
                  delete copy[event.node_id!];
                }
                return copy;
              });
            }
          },
          onProgress: (progress, stage, msg) => {
            // Deprecated callback fallback, everything handled in onStageEvent
          },
          onContent: (chunk) => {
            accumulatedText = chunk;
          },
          onCitations: (citations) => {
            citationsAccumulator = citations;
            setActiveCitations(citations);
          },
          onComplete: (finalText, citations) => {
            setStreamStatus("completed");
            setStreamStage("completed");
            setStreamProgress(100);

            // Clean up any existing typing timer just in case
            if (typingTimerRef.current) {
              clearInterval(typingTimerRef.current);
            }

            // Start streaming animation word by word
            const words = finalText.split(/(\s+)/); // Preserves spacing
            let wordIndex = 0;
            let currentText = "";

            typingTimerRef.current = setInterval(() => {
              if (wordIndex < words.length) {
                currentText += words[wordIndex];
                setCurrentAssistantText(currentText);
                wordIndex++;
              } else {
                if (typingTimerRef.current) {
                  clearInterval(typingTimerRef.current);
                  typingTimerRef.current = null;
                }

                // Done typing, commit message to history
                setIsSending(false);

                const assistantMessage: MessageItem = {
                  id: `assistant-${Date.now()}`,
                  session_id: sessionId,
                  user_id: "assistant",
                  role: "assistant",
                  content: finalText,
                  created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, assistantMessage]);
                setCurrentAssistantText("");
                setActiveCitations([]);
                setCompletedStages([]);
                setActiveNodes({});
                setPublicRequestSummary(null);
                setStageMetadata({});
                abortControllerRef.current = null;
              }
            }, 25); // 25ms interval per word chunk
          },
          onError: (err: ApiError) => {
            setIsSending(false);
            setStreamStatus("failed");
            setStreamStage("failed");
            setStageMetadata((prev) => ({ ...prev, error_message: err.message || "Failed to receive response from AI." }));
            toast.error(err.message || "Failed to receive response from AI.");
            abortControllerRef.current = null;
          },
        },
        controller.signal
      );
    } catch (err: any) {
      setIsSending(false);
      setStreamStatus("failed");
      setStreamStage("failed");
      setStageMetadata((prev) => ({ ...prev, error_message: err.message || "Failed to receive response from AI." }));
      abortControllerRef.current = null;
    }
  };

  return {
    sessionId,
    messages,
    isLoadingHistory,
    isSending,
    streamStage,
    streamProgress,
    streamStatus,
    activeCitations,
    currentAssistantText,
    completedStages,
    activeNodes,
    publicRequestSummary,
    stageMetadata,
    sendMessage,
    stopStreaming: cancelCurrentStream,
    refreshHistory: () => documentId && userId && initializeSessionAndHistory(documentId, userId),
    startNewChat,
    loadChatSession,
  };
}
