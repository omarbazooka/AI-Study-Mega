"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { documentsService } from "@/services/documents.service";
import { aiService } from "@/services/ai.service";
import type { DocumentListItem, StatusResponse } from "@/types/api/documents";

function formatError(error: unknown): string {
  if (!error) return "Unknown error";
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    const value = error as Record<string, unknown>;
    const parts = [
      value.code ? `code=${String(value.code)}` : "",
      value.status !== undefined ? `status=${String(value.status)}` : "",
      value.message ? String(value.message) : "",
    ].filter(Boolean);
    if (parts.length) return parts.join(" · ");
  }
  return String(error);
}

function detectLanguage(text: string): "ar" | "en" {
  return /[\u0600-\u06FF]/.test(text) ? "ar" : "en";
}

export default function AITestClient() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [backendState, setBackendState] = useState<"checking" | "ok" | "error">("checking");
  const [backendMessage, setBackendMessage] = useState("Checking authenticated backend access...");
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("What is this document mainly about?");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const sessionId = useRef<string>(crypto.randomUUID());
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedId) ?? null,
    [documents, selectedId]
  );

  async function refreshDocuments(preferredId?: string) {
    try {
      const data = await documentsService.listDocuments();
      setDocuments(data.items);
      setBackendState("ok");
      setBackendMessage(`Backend authenticated successfully. ${data.total} document(s) found.`);
      setError("");

      const nextId =
        preferredId ||
        (selectedId && data.items.some((item) => item.id === selectedId) ? selectedId : data.items[0]?.id) ||
        "";
      setSelectedId(nextId);
      return data.items;
    } catch (err) {
      const message = formatError(err);
      setBackendState("error");
      setBackendMessage(message);
      setError(`Backend check failed: ${message}`);
      return [];
    }
  }

  async function loadStatus(documentId: string) {
    if (!documentId) return null;
    try {
      const next = await documentsService.getDocumentStatus(documentId);
      setStatus(next);
      return next;
    } catch (err) {
      setError(`Status check failed: ${formatError(err)}`);
      return null;
    }
  }

  function stopPolling() {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }

  async function pollUntilDone(documentId: string) {
    stopPolling();
    const next = await loadStatus(documentId);
    if (!next) return;

    if (next.status === "ready" || next.status === "failed") {
      await refreshDocuments(documentId);
      return;
    }

    pollTimer.current = setTimeout(() => pollUntilDone(documentId), 2500);
  }

  useEffect(() => {
    refreshDocuments();
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setStatus(null);
      return;
    }
    loadStatus(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setError("");
    setAnswer("");

    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }

    setUploading(true);
    try {
      const result = await documentsService.uploadDocument(file);
      setSelectedId(result.document_id);
      setBackendState("ok");
      setBackendMessage(`Upload accepted: ${result.message}`);
      await refreshDocuments(result.document_id);
      await pollUntilDone(result.document_id);
    } catch (err) {
      setError(`Upload failed: ${formatError(err)}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk() {
    if (!selectedId) {
      setError("Upload or select a document first.");
      return;
    }
    if (status?.status !== "ready") {
      setError(`Document is not ready yet. Current status: ${status?.status ?? "unknown"}`);
      return;
    }
    if (!question.trim()) return;

    setAsking(true);
    setError("");
    setAnswer("");
    try {
      const response = await aiService.sendChat(selectedId, {
        session_id: sessionId.current,
        message: question.trim(),
        language: detectLanguage(question),
        request_source: "production_ai_test",
      });
      setAnswer(response.message || "AI returned an empty response.");
    } catch (err) {
      setError(`AI request failed: ${formatError(err)}`);
    } finally {
      setAsking(false);
    }
  }

  const stateClass =
    backendState === "ok"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
      : backendState === "error"
        ? "border-red-500/40 bg-red-500/10 text-red-200"
        : "border-amber-500/40 bg-amber-500/10 text-amber-200";

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 px-5 py-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-violet-400">Production smoke test</p>
            <h1 className="mt-2 text-3xl font-semibold">Test the AI pipeline</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Upload a PDF, wait for ingestion to reach ready, then ask a grounded question.
            </p>
          </div>
          <Link href="/dashboard" className="rounded-lg border border-zinc-700 px-4 py-2 text-sm hover:bg-zinc-900">
            Back to dashboard
          </Link>
        </div>

        <section className={`rounded-xl border p-4 text-sm ${stateClass}`}>
          <div className="font-medium">Backend / Auth status</div>
          <div className="mt-1 break-words opacity-90">{backendMessage}</div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h2 className="text-lg font-medium">1. Upload PDF</h2>
          <input
            className="mt-4 block w-full rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-violet-600 file:px-4 file:py-2 file:text-white"
            type="file"
            accept="application/pdf,.pdf"
            disabled={uploading}
            onChange={(event) => handleUpload(event.target.files?.[0])}
          />
          <p className="mt-3 text-xs text-zinc-500">{uploading ? "Uploading..." : "Maximum configured upload size: 10 MB."}</p>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-medium">2. Document ingestion</h2>
            <button
              type="button"
              onClick={() => refreshDocuments()}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs hover:bg-zinc-800"
            >
              Refresh
            </button>
          </div>

          {documents.length > 0 ? (
            <select
              value={selectedId}
              onChange={(event) => setSelectedId(event.target.value)}
              className="mt-4 w-full rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm"
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.original_filename} — {doc.upload_status}
                </option>
              ))}
            </select>
          ) : (
            <p className="mt-4 text-sm text-zinc-500">No documents yet.</p>
          )}

          {selectedDocument && (
            <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm">
              <div className="rounded-lg bg-zinc-950 p-3">
                <div className="text-zinc-500">Status</div>
                <div className="mt-1 font-medium">{status?.status ?? selectedDocument.upload_status}</div>
              </div>
              <div className="rounded-lg bg-zinc-950 p-3">
                <div className="text-zinc-500">Pages</div>
                <div className="mt-1 font-medium">{status?.page_count ?? selectedDocument.page_count ?? 0}</div>
              </div>
              <div className="rounded-lg bg-zinc-950 p-3">
                <div className="text-zinc-500">Chunks</div>
                <div className="mt-1 font-medium">{status?.chunk_count ?? selectedDocument.chunk_count ?? 0}</div>
              </div>
            </div>
          )}

          {status?.error_message && (
            <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
              {status.error_message}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h2 className="text-lg font-medium">3. Ask the AI</h2>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            className="mt-4 w-full rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm outline-none focus:border-violet-500"
            placeholder="Ask something grounded in the uploaded PDF..."
          />
          <button
            type="button"
            disabled={asking || status?.status !== "ready"}
            onClick={handleAsk}
            className="mt-3 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {asking ? "Asking AI..." : "Ask AI"}
          </button>

          {answer && (
            <div className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400">AI answer</div>
              <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-200">{answer}</div>
            </div>
          )}

          {error && (
            <div className="mt-5 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
              {error}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
