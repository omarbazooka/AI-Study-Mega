/* eslint-disable @typescript-eslint/no-explicit-any */
import { backendClient } from "./backend-client";
import { AIResponse, PDFChatRequest, SummaryRequest, NDJSONStreamEvent } from "@/types/api/ai";
import { QuizRequest } from "@/types/api/quiz";
import { ApiError } from "@/types/api/common";

export interface StreamHandlers {
  onProgress?: (progress: number, stage: string, message: string) => void;
  onTaskStarted?: (taskId: string, taskType: string, message: string) => void;
  onTaskCompleted?: (taskId: string, taskType: string) => void;
  onTaskFailed?: (taskId: string, taskType: string, error: string) => void;
  onContent?: (content: string) => void;
  onCitations?: (citations: any[]) => void;
  onComplete?: (finalContent: string, citations: any[]) => void;
  onError?: (error: any) => void;
  onStageEvent?: (event: NDJSONStreamEvent) => void;
}

export const aiService = {
  async sendChat(documentId: string, payload: PDFChatRequest): Promise<AIResponse> {
    return backendClient.post<AIResponse>(`/api/v1/documents/${documentId}/chat`, payload);
  },

  async generateSummary(documentId: string, payload: SummaryRequest): Promise<AIResponse> {
    return backendClient.post<AIResponse>(`/api/v1/documents/${documentId}/summary`, payload);
  },

  async generateQuiz(documentId: string, payload: QuizRequest): Promise<AIResponse> {
    return backendClient.post<AIResponse>(`/api/v1/documents/${documentId}/quiz`, payload);
  },

  async streamChat(
    documentId: string,
    payload: PDFChatRequest,
    handlers: StreamHandlers,
    signal?: AbortSignal
  ): Promise<void> {
    try {
      const response = await backendClient.stream(`/api/v1/documents/${documentId}/chat/stream`, payload, { signal });

      if (!response.body) {
        throw new Error("Response body is not readable.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let completedSuccessfully = false;
      let finalContent = "";
      let finalCitations: any[] = [];
      let streamFailure: ApiError | null = null;

      const processEvent = (event: NDJSONStreamEvent) => {
        handlers.onStageEvent?.(event);
        handlers.onProgress?.(event.progress, event.stage, event.message || "");

        if (event.node_id) {
          if (event.status === "started") {
            handlers.onTaskStarted?.(event.node_id, event.stage, event.message || "");
          } else if (event.status === "completed") {
            handlers.onTaskCompleted?.(event.node_id, event.stage);
          } else if (event.status === "failed") {
            handlers.onTaskFailed?.(event.node_id, event.stage, event.message || "");
          }
        }

        if (event.content !== undefined) {
          finalContent = event.content;
          handlers.onContent?.(event.content);
        }

        if (event.citations) {
          finalCitations = event.citations;
          handlers.onCitations?.(event.citations);
        }

        if (event.stage === "failed" || event.status === "failed") {
          streamFailure = {
            status: 500,
            code: "BACKEND_PIPELINE_FAILED",
            message: event.message || "The AI backend pipeline failed.",
          } as ApiError;
          return;
        }

        if (event.stage === "completed" && event.status === "completed") {
          completedSuccessfully = true;
          handlers.onComplete?.(finalContent, finalCitations);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          try {
            processEvent(JSON.parse(trimmed) as NDJSONStreamEvent);
          } catch (e) {
            if (process.env.NODE_ENV !== "production") {
              console.warn("Failed to parse NDJSON line:", trimmed, e);
            }
          }
        }
      }

      if (buffer.trim()) {
        try {
          processEvent(JSON.parse(buffer) as NDJSONStreamEvent);
        } catch {
          // Ignore a malformed trailing fragment; a successful completion event
          // or a concrete failed event below determines the final state.
        }
      }

      if (streamFailure) {
        throw streamFailure;
      }

      if (!completedSuccessfully) {
        throw {
          status: 500,
          code: "STREAM_INCOMPLETE",
          message: "The chat stream ended before the backend sent a completion event.",
        } as ApiError;
      }
    } catch (err: any) {
      if (signal?.aborted) return;
      if (handlers.onError) {
        handlers.onError(err);
      } else {
        throw err;
      }
    }
  }
};
