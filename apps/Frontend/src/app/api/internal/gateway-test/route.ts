import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET(request: Request) {
  const url = new URL(request.url);
  if (url.searchParams.get("key") !== "gateway-2af631") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const token = process.env.AI_GATEWAY_API_KEY || process.env.VERCEL_OIDC_TOKEN;
  if (!token) {
    return NextResponse.json({ ok: false, reason: "NO_GATEWAY_TOKEN" });
  }

  const modelsRes = await fetch("https://ai-gateway.vercel.sh/v1/models", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const modelsBody = await modelsRes.json().catch(() => ({}));
  const models = Array.isArray((modelsBody as any)?.data) ? (modelsBody as any).data : [];
  const candidates = [
    "openai/gpt-5-nano",
    "openai/gpt-4.1-nano",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-oss-20b",
  ];
  const available = candidates.filter((id) => models.some((m: any) => m.id === id));

  if (url.searchParams.get("run") !== "1") {
    return NextResponse.json({
      ok: modelsRes.ok,
      status: modelsRes.status,
      modelCount: models.length,
      available,
      sample: models.slice(0, 10).map((m: any) => m.id),
    });
  }

  const model = available[0] || models[0]?.id;
  if (!model) return NextResponse.json({ ok: false, reason: "NO_MODELS" });

  const response = await fetch("https://ai-gateway.vercel.sh/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: [{ role: "user", content: "Reply with exactly: GATEWAY_OK" }],
      temperature: 0,
      max_tokens: 16,
    }),
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  return NextResponse.json({
    ok: response.ok,
    status: response.status,
    model,
    content: (body as any)?.choices?.[0]?.message?.content || null,
    error: response.ok ? null : body,
  });
}
