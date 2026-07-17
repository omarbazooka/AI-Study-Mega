/* eslint-disable @typescript-eslint/no-explicit-any */
export type TaskType = 
  | "chat_answer"
  | "explain"
  | "summary"
  | "quiz"
  | "key_points"
  | "comparison_table"
  | "answer_table"
  | "flashcards"
  | "answer_evaluation"
  | "clarification"
  | "out_of_scope"
  | "unknown";

export type ExecutionMode = "single" | "parallel" | "sequential" | "hybrid";

export interface Citation {
  chunk_id: string;
  page_number: number;
  section_title?: string | null;
  snippet?: string | null;
  score?: number | null;
}

export interface TaskResult {
  task_id: string;
  type: TaskType;
  status: string; // "success", "failed", "partial", etc.
  content: unknown;
  citations: Citation[];
  confidence: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AIResponse {
  status: string; // "success", "failed", "partial", etc.
  message: string;
  execution_mode: ExecutionMode;
  tasks: TaskResult[];
  citations: Citation[];
  confidence: number;
  error?: string | null;
  metadata?: {
    quiz?: any; // Structured quiz data is read only from metadata.quiz
    [key: string]: unknown;
  };
  pipeline_trace?: Record<string, unknown> | null;
}

export interface PDFChatRequest {
  session_id: string;
  message: string;
  language?: "ar" | "en";
  user_level?: string;
  request_source?: string;
}

export interface SummaryRequest {
  session_id: string;
  language?: "ar" | "en";
  user_level?: string;
  summary_style?: "bullet_points" | "paragraph" | null;
  summary_size?: "concise" | "medium" | "detailed";
}

export interface NDJSONStreamEvent {
  request_id: string;
  node_id?: string | null;
  stage: string;
  status: "started" | "progress" | "completed" | "failed" | "cancelled";
  message?: string;
  progress: number;
  timestamp: string;
  content?: string;
  citations?: Array<{
    chunk_id: string;
    page_number: number;
    section_title?: string | null;
    score?: number | null;
  }>;
  confidence?: number;
  metadata?: Record<string, any>;
}
