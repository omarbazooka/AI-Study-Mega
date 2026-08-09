import { NextResponse } from "next/server";
import { randomUUID } from "crypto";
import {
  SUPABASE_PUBLISHABLE_KEY,
  SUPABASE_URL,
} from "@/lib/supabase/config";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const BACKEND = "https://back-end-production-7371.up.railway.app";
const TEST_EMAIL = "ai.study.e2e.20260809@gmail.com";
const TEST_PASSWORD = "E2E-only-4Yp!82kQ";
const PDF_BASE64 = "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA2IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9QYWdlTW9kZSAvVXNlTm9uZSAvUGFnZXMgNiAwIFIgL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0F1dGhvciAoYW5vbnltb3VzKSAvQ3JlYXRpb25EYXRlIChEOjIwMjYwODA5MDUwNzI2KzAwJzAwJykgL0NyZWF0b3IgKGFub255bW91cykgL0tleXdvcmRzICgpIC9Nb2REYXRlIChEOjIwMjYwODA5MDUwNzI2KzAwJzAwJykgL1Byb2R1Y2VyIChSZXBvcnRMYWIgUERGIExpYnJhcnkgLSBcKG9wZW5zb3VyY2VcKSkgCiAgL1N1YmplY3QgKHVuc3BlY2lmaWVkKSAvVGl0bGUgKHVudGl0bGVkKSAvVHJhcHBlZCAvRmFsc2UKPj4KZW5kb2JqCjYgMCBvYmoKPDwKL0NvdW50IDEgL0tpZHMgWyAzIDAgUiBdIC9UeXBlIC9QYWdlcwo+PgplbmRvYmoKNyAwIG9iago8PAovRmlsdGVyIFsgL0FTQ0lJODVEZWNvZGUgL0ZsYXRlRGVjb2RlIF0gL0xlbmd0aCAzNTUKPj4Kc3RyZWFtCkdhczJEOTJFR1omOzlOTidsc01SUTklVltmLSFDWldJUFs2bWAqcDpMO10sTS4ubEVXVWZHQy03QCglKkNBKy1mQVhMTllgYTxvKSIzOj9SIiYkRkZZXVExX0Rpc1dfbSdEbXRRIWgiZUs2T2lJMkwraGUzWnE0PUUsbSJcN1lacjFeQk9XP15VbDFnL0I6V0UuIzcpYDddXzY7JEpvL2Q8bi5ITUw8cy4nIm1NPCIuJ2l1Z2xEW2RQQiVRIzVqOS1oaVAqWiJYVmtiLllJOkl1K188bllTP0FhLDZEVmp1KlJdWzxJKlAsTFhjVlM+LU48IW1DLG1SKzhoQ0A2OygwVDkhOFJkRisxdGc6Ris2RmIxMVhBUmFUPXUlNF05bGs0TWJAdSlOJDU5PUAjbWU8QGIhcmMuJG1aVD9PZS9XKWJVX1xnWy1lPzgrV1s7JUFEVDpmdFVhIW5kRWdTT3Vpfj5lbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA4CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDA2MSAwMDAwMCBuIAowMDAwMDAwMDkyIDAwMDAwIG4gCjAwMDAwMDAxOTkgMDAwMDAgbiAKMDAwMDAwMDM5MiAwMDAwMCBuIAowMDAwMDAwNDYwIDAwMDAwIG4gCjAwMDAwMDA3MjEgMDAwMDAgbiAKMDAwMDAwMDc4MCAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9JRCAKWzwwMThjYzdhYTgwZDA2Mjc5MDM2NDRiN2JjODMwNDU3Mj48MDE4Y2M3YWE4MGQwNjI3OTAzNjQ0YjdiYzgzMDQ1NzI+XQolIFJlcG9ydExhYiBnZW5lcmF0ZWQgUERGIGRvY3VtZW50IC0tIGRpZ2VzdCAob3BlbnNvdXJjZSkKCi9JbmZvIDUgMCBSCi9Sb290IDQgMCBSCi9TaXplIDgKPj4Kc3RhcnR4cmVmCjEyMjUKJSVFT0YK";

const headers = { apikey: SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json" };

async function authToken() {
  const signIn = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers,
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
    cache: "no-store",
  });
  if (signIn.ok) return { ok: true as const, data: await signIn.json() };

  const signup = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers,
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
    cache: "no-store",
  });
  const data = await signup.json().catch(() => ({}));
  if (signup.ok && data?.access_token) return { ok: true as const, data };
  return { ok: false as const, signInStatus: signIn.status, signupStatus: signup.status, data };
}

async function api(path: string, token: string, init: RequestInit = {}) {
  const res = await fetch(`${BACKEND}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init.headers || {}),
    },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = text;
  try { body = JSON.parse(text); } catch {}
  return { status: res.status, ok: res.ok, body };
}

export async function GET(request: Request) {
  const u = new URL(request.url);
  if (u.searchParams.get("key") !== "e2e-74c9f6") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const auth = await authToken();
  if (!auth.ok) {
    return NextResponse.json({ phase: "auth", ...auth }, { status: 200 });
  }
  const token = auth.data.access_token as string;

  const listBefore = await api("/api/v1/documents", token);
  if (!listBefore.ok) return NextResponse.json({ phase: "backend_auth", listBefore });

  const form = new FormData();
  form.append("file", new Blob([Buffer.from(PDF_BASE64, "base64")], { type: "application/pdf" }), "production-e2e.pdf");
  const upload = await api("/api/v1/documents/upload", token, { method: "POST", body: form });
  if (!upload.ok) return NextResponse.json({ phase: "upload", upload, listBefore });

  const documentId = (upload.body as any)?.document_id as string;
  let statusResp: any = null;
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    statusResp = await api(`/api/v1/documents/${documentId}/status`, token);
    if ((statusResp.body as any)?.status === "ready" || (statusResp.body as any)?.status === "failed") break;
  }
  if ((statusResp?.body as any)?.status !== "ready") {
    return NextResponse.json({ phase: "ingestion", upload, statusResp });
  }

  const sessionId = randomUUID();
  const jsonHeaders = { "Content-Type": "application/json" };

  const chat = await api(`/api/v1/documents/${documentId}/chat`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, message: "What is the secret verification phrase in this document?", language: "en" }),
  });

  const streamRes = await fetch(`${BACKEND}/api/v1/documents/${documentId}/chat/stream`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: "What course topic is stated in the document?", language: "en" }),
    cache: "no-store",
  });
  const streamText = await streamRes.text();
  const streamLines = streamText.split("\n").filter(Boolean).map((line) => {
    try { return JSON.parse(line); } catch { return { raw: line }; }
  });
  const streamCompleted = streamLines.some((e: any) => e.stage === "completed" && e.status === "completed");
  const streamFailed = streamLines.find((e: any) => e.status === "failed");

  const summary = await api(`/api/v1/documents/${documentId}/summary`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, language: "en", summary_style: "bullet_points" }),
  });

  const quiz = await api(`/api/v1/documents/${documentId}/quiz`, token, {
    method: "POST", headers: jsonHeaders,
    body: JSON.stringify({ session_id: sessionId, language: "en", difficulty: "easy", number_of_questions: 3, question_type: "multiple_choice" }),
  });

  return NextResponse.json({
    phase: "complete",
    backendList: listBefore.status,
    ingestion: statusResp,
    chat,
    stream: { status: streamRes.status, completed: streamCompleted, failed: streamFailed || null, tail: streamLines.slice(-5) },
    summary,
    quiz,
    documentId,
    sessionId,
  });
}
