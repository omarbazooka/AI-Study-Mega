/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useState, useEffect } from "react";
import { User } from "@supabase/supabase-js";
import { useDocuments } from "@/hooks/useDocuments";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";
import { useDocumentStatus } from "@/hooks/useDocumentStatus";
import { useAIChatStream } from "@/hooks/useAIChatStream";

import { DocumentControls } from "./DocumentControls";
import { DocumentStatus } from "./DocumentStatus";
import { ChatView } from "./ChatView";
import { ChatComposer } from "./ChatComposer";
import { PipelineStatus } from "./PipelineStatus";
import { SummaryView } from "./SummaryView";
import { QuizView } from "./QuizView";
import { HistoryView } from "./HistoryView";

import { MessageSquare, FileText, Award, Clock, Plus } from "lucide-react";

const detectLanguage = (text: string): "ar" | "en" => {
  const arabicRegex = /[\u0600-\u06FF]/;
  return arabicRegex.test(text) ? "ar" : "en";
};

interface AIPanelContainerProps {
  user: User;
  activePageId?: string;
  activePageTitle?: string;
  activePageContent?: string;
  onUpdatePage?: (id: string, updates: { content?: string; title?: string }) => void;
}

export const AIPanelContainer: React.FC<AIPanelContainerProps> = ({ 
  user,
  activePageId,
  activePageTitle,
  activePageContent,
  onUpdatePage,
}) => {
  const [activeTab, setActiveTab] = useState<"chat" | "summary" | "quiz">("chat");
  const [showHistory, setShowHistory] = useState(false);

  const {
    documents,
    isLoading: isDocsLoading,
    activeDocumentId,
    activeDocument,
    setActiveDocumentId,
    refreshDocuments,
  } = useDocuments();

  useEffect(() => {
    setShowHistory(false);
  }, [activeDocumentId]);

  const {
    uploadFile,
    isUploading,
    error: uploadError,
  } = useDocumentUpload({
    onUploadSuccess: async (newDocId) => {
      await refreshDocuments();
      setActiveDocumentId(newDocId);
    },
  });

  const {
    status: docStatus,
    details: docDetails,
    isReprocessing,
    reprocess,
  } = useDocumentStatus(activeDocumentId, activeDocument?.upload_status, isDocsLoading, {
    onReady: () => {
      refreshDocuments();
    },
  });

  const isReady = docStatus === "ready";

  const {
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
    stopStreaming,
    startNewChat,
    loadChatSession,
  } = useAIChatStream({
    documentId: activeDocumentId,
    userId: user?.id || null,
    documentReady: isReady,
  });

  return (
    <aside className="w-[420px] h-[calc(100vh-40px)] ml-0 bg-background/20 backdrop-blur-sm border border-[#666565]/50 rounded-lg flex flex-col m-[20px] relative shrink-0 overflow-hidden shadow-2xl">
      {/* ── Document Controls & Upload ───────────────────────── */}
      <DocumentControls
        documents={documents}
        activeDocumentId={activeDocumentId}
        onSelectDocument={setActiveDocumentId}
        onUploadFile={uploadFile}
        isUploading={isUploading}
        uploadError={uploadError}
      />

      {/* ── Ingestion status banner ──────────────────────────── */}
      <DocumentStatus
        status={docStatus}
        errorMessage={docDetails?.error_message}
        onReprocess={reprocess}
        isReprocessing={isReprocessing}
      />

      {/* ── Tab Switcher ────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/20 px-4 py-1.5">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-primary text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Discuss
          </button>

          <button
            onClick={() => setActiveTab("summary")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide transition-all cursor-pointer ${
              activeTab === "summary"
                ? "bg-primary text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            Summary
          </button>

          <button
            onClick={() => setActiveTab("quiz")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide transition-all cursor-pointer ${
              activeTab === "quiz"
                ? "bg-primary text-white"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Award className="h-3.5 w-3.5" />
            Practice Quiz
          </button>
        </div>

        {activeTab === "chat" && isReady && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`p-1.5 rounded-full transition-colors cursor-pointer ${
                showHistory 
                  ? "bg-zinc-800 text-primary" 
                  : "text-zinc-500 hover:bg-zinc-900/60 hover:text-zinc-300"
              }`}
              title="Chat History"
            >
              <Clock className="h-4 w-4" />
            </button>
            <button
              onClick={startNewChat}
              className="p-1.5 rounded-full text-zinc-500 hover:bg-zinc-900/60 hover:text-zinc-300 transition-colors cursor-pointer"
              title="New Chat"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* ── Tab Render Body ──────────────────────────────────── */}
      {activeTab === "chat" && (
        <>
          {showHistory ? (
            <HistoryView
              documentId={activeDocumentId}
              onSelectSession={(id) => {
                loadChatSession(id);
                setShowHistory(false);
              }}
              onClose={() => setShowHistory(false)}
            />
          ) : (
            <>
              <ChatView
                messages={messages}
                currentAssistantText={currentAssistantText}
                activeCitations={activeCitations}
                isSending={isSending}
                isLoadingHistory={isLoadingHistory}
                streamStage={streamStage}
                streamProgress={streamProgress}
                streamStatus={streamStatus}
                completedStages={completedStages}
                publicRequestSummary={publicRequestSummary}
                stageMetadata={stageMetadata}
              />

              <ChatComposer
                onSend={(txt) => sendMessage(txt, detectLanguage(txt))}
                isSending={isSending}
                disabled={!isReady || isDocsLoading}
                onStop={stopStreaming}
              />
            </>
          )}
        </>
      )}

      {activeTab === "summary" && (
        <SummaryView
          documentId={activeDocumentId}
          sessionId={sessionId || "summary-session"}
          disabled={!isReady}
          activePageId={activePageId}
          activePageTitle={activePageTitle}
          activePageContent={activePageContent}
          documentName={activeDocument?.original_filename}
          onUpdatePage={onUpdatePage}
        />
      )}

      {activeTab === "quiz" && (
        <QuizView
          documentId={activeDocumentId}
          sessionId={sessionId || "quiz-session"}
          disabled={!isReady}
        />
      )}
    </aside>
  );
};
