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
 
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
 
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer
 
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
 
          try {
            const event: NDJSONStreamEvent = JSON.parse(trimmed);
            
            if (handlers.onStageEvent) {
              handlers.onStageEvent(event);
            }
 
            // Invoke handlers based on event stage/status
            if (handlers.onProgress) {
              handlers.onProgress(event.progress, event.stage, event.message || "");
            }

            if (event.node_id) {
              if (event.status === "started" && handlers.onTaskStarted) {
                handlers.onTaskStarted(event.node_id, event.stage, event.message || "");
              } else if (event.status === "completed" && handlers.onTaskCompleted) {
                handlers.onTaskCompleted(event.node_id, event.stage);
              } else if (event.status === "failed" && handlers.onTaskFailed) {
                handlers.onTaskFailed(event.node_id, event.stage, event.message || "");
              }
            }

            // Expose content if present
            if (event.content !== undefined) {
              finalContent = event.content;
              if (handlers.onContent) {
                handlers.onContent(event.content);
              }
            }

            // Expose citations if present
            if (event.citations) {
              finalCitations = event.citations;
              if (handlers.onCitations) {
                handlers.onCitations(event.citations);
              }
            }

            // Detect final completed event
            if (event.stage === "completed" && event.status === "completed") {
              completedSuccessfully = true;
              if (handlers.onComplete) {
                handlers.onComplete(finalContent, finalCitations);
              }
            }
          } catch (e) {
            // Do not log malformed raw lines in production
            if (process.env.NODE_ENV !== "production") {
              console.warn("Failed to parse NDJSON line:", trimmed, e);
            }
          }
        }
      }

      // Handle final buffer remainder
      if (buffer.trim()) {
        try {
          const event: NDJSONStreamEvent = JSON.parse(buffer);
          if (event.content !== undefined) {
            finalContent = event.content;
            if (handlers.onContent) handlers.onContent(event.content);
          }
          if (event.citations) {
            finalCitations = event.citations;
            if (handlers.onCitations) handlers.onCitations(event.citations);
          }
          if (event.stage === "completed" && event.status === "completed") {
            completedSuccessfully = true;
            if (handlers.onComplete) handlers.onComplete(finalContent, finalCitations);
          }
        } catch {
          // ignore
        }
      }

      if (!completedSuccessfully) {
        throw {
          status: 500,
          code: "STREAM_INCOMPLETE",
          message: "The chat stream ended abruptly before completion.",
        } as ApiError;
      }
    } catch (err: any) {
      if (signal?.aborted) {
        // Request was cancelled, do not trigger error handlers
        return;
      }
      if (handlers.onError) {
        handlers.onError(err);
      } else {
        throw err;
      }
    }
  }
};
