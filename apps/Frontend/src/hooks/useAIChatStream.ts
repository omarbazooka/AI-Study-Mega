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
    setStreamStage("Initializing");
    setStreamProgress(0);
    setStreamStatus("started");
    setCurrentAssistantText("");
    setActiveCitations([]);

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
          onProgress: (progress, stage, msg) => {
            setStreamProgress(progress);
            setStreamStage(stage);
            setStreamStatus("progress");
          },
          onContent: (chunk) => {
            accumulatedText = chunk;
            // Do not immediately flash the full text to avoid flashing prior to typing animation.
          },
          onCitations: (citations) => {
            citationsAccumulator = citations;
            setActiveCitations(citations);
          },
          onComplete: (finalText, citations) => {
            setStreamStatus("completed");
            setStreamStage("Completed");
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
                abortControllerRef.current = null;
              }
            }, 25); // 25ms interval per word chunk
          },
          onError: (err: ApiError) => {
            setIsSending(false);
            setStreamStatus("failed");
            setStreamStage("Failed");
            toast.error(err.message || "Failed to receive response from AI.");
            abortControllerRef.current = null;
          },
        },
        controller.signal
      );
    } catch (err: any) {
      setIsSending(false);
      setStreamStatus("failed");
      setStreamStage("Failed");
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
    sendMessage,
    stopStreaming: cancelCurrentStream,
    refreshHistory: () => documentId && userId && initializeSessionAndHistory(documentId, userId),
    startNewChat,
    loadChatSession,
  };
}
