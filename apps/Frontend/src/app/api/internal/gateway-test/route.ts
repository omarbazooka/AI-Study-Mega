import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET(request: Request) {
  const url = new URL(request.url);
  if (url.searchParams.get("key") !== "gateway-2af631") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const res = await fetch("https://back-end-production-7371.up.railway.app/internal/llm-health/llm-probe-93fd2b", { cache: "no-store" });
  const text = await res.text();
  let body: unknown = text;
  try { body = JSON.parse(text); } catch {}
  return NextResponse.json({ status: res.status, ok: res.ok, body });
}
