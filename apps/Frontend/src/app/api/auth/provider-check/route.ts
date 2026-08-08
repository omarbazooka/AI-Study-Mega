import { NextResponse } from "next/server";
import {
  SUPABASE_PUBLISHABLE_KEY,
  SUPABASE_URL,
} from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

async function checkProvider(provider: "google" | "github") {
  const redirectTo = "https://ai-study-mega.vercel.app/auth/callback";
  const url = new URL(`${SUPABASE_URL}/auth/v1/authorize`);
  url.searchParams.set("provider", provider);
  url.searchParams.set("redirect_to", redirectTo);

  const response = await fetch(url, {
    headers: { apikey: SUPABASE_PUBLISHABLE_KEY },
    redirect: "manual",
    cache: "no-store",
  });

  const location = response.headers.get("location");
  let redirectHost: string | null = null;
  let redirectPath: string | null = null;

  if (location) {
    try {
      const parsed = new URL(location);
      redirectHost = parsed.host;
      redirectPath = parsed.pathname;
    } catch {
      // Leave fields null if upstream returns a relative/malformed location.
    }
  }

  return {
    status: response.status,
    redirects: response.status >= 300 && response.status < 400,
    redirectHost,
    redirectPath,
  };
}

export async function GET() {
  const settingsResponse = await fetch(`${SUPABASE_URL}/auth/v1/settings`, {
    headers: { apikey: SUPABASE_PUBLISHABLE_KEY },
    cache: "no-store",
  });
  const settings = await settingsResponse.json().catch(() => ({}));
  const external = settings?.external ?? {};

  const [google, github] = await Promise.all([
    checkProvider("google"),
    checkProvider("github"),
  ]);

  return NextResponse.json({
    supabaseReachable: settingsResponse.ok,
    googleEnabled: Boolean(external.google),
    githubEnabled: Boolean(external.github),
    google,
    github,
  });
}
