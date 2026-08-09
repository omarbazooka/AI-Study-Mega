import { NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "@/lib/supabase/config";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const BACKEND = "https://back-end-production-7371.up.railway.app";
const TEST_EMAIL = "ai.study.e2e.20260809@gmail.com";
const TEST_PASSWORD = "E2E-only-4Yp!82kQ";
const DOCUMENT_ID = "11111111-2222-4333-8444-555555555555";
const authHeaders = { apikey: SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json" };

async function authToken() {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

async function api(path: string, token: string, init: RequestInit = {}) {
  const res = await fetch(`${BACKEND}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init.headers || {}) },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = text;
  try { body = JSON.parse(text); } catch {}
  return { status: res.status, ok: res.ok, body };
}

export async function GET(request: Request) {
  const u = new URL(request.url);
  if (u.searchParams.get("key") !== "e2e-74c9f6") return NextResponse.json({ error: "not found" }, { status: 404 });

  const auth = await authToken();
  if (!auth.ok) return NextResponse.json({ phase: "auth", auth });
  const token = auth.data.access_token as string;
  const jsonHeaders = { "Content-Type": "application/json" };
  const list = await api("/api/v1/documents", token);
  const status = await api(`/api/v1/documents/${DOCUMENT_ID}/status`, token);
  const sessionId = randomUUID();

  const chat = await api(`/api/v1/documents/${DOCUMENT_ID}/chat`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, message: "Explain what this certificate says the learner completed.", language: "en" }),
  });

  const streamRes = await fetch(`${BACKEND}/api/v1/documents/${DOCUMENT_ID}/chat/stream`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: "What learning topic is stated on the certificate?", language: "en" }),
    cache: "no-store",
  });
  const streamText = await streamRes.text();
  const streamLines = streamText.split("\n").filter(Boolean).map((line) => { try { return JSON.parse(line); } catch { return { raw: line }; } });
  const streamCompleted = streamLines.some((e: any) => e.stage === "completed" && e.status === "completed");
  const streamFailed = streamLines.filter((e: any) => e.status === "failed");

  const summary = await api(`/api/v1/documents/${DOCUMENT_ID}/summary`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, language: "en", summary_style: "bullet_points" }),
  });

  const quiz = await api(`/api/v1/documents/${DOCUMENT_ID}/quiz`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, language: "en", difficulty: "easy", number_of_questions: 3, question_type: "multiple_choice" }),
  });

  return NextResponse.json({ phase: "complete", list, status, chat, stream: { status: streamRes.status, completed: streamCompleted, failed: streamFailed, tail: streamLines.slice(-8) }, summary, quiz, sessionId });
}
