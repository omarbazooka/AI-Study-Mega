import { NextResponse } from "next/server";
import {
  SUPABASE_PUBLISHABLE_KEY,
  SUPABASE_URL,
} from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(`${SUPABASE_URL}/auth/v1/settings`, {
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
      },
      cache: "no-store",
    });

    const payload = await response.json().catch(() => ({}));
    const external = payload?.external ?? {};

    return NextResponse.json(
      {
        supabaseReachable: response.ok,
        status: response.status,
        google: Boolean(external.google),
        github: Boolean(external.github),
      },
      { status: response.ok ? 200 : 502 }
    );
  } catch (error: unknown) {
    return NextResponse.json(
      {
        supabaseReachable: false,
        status: 0,
        google: false,
        github: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 502 }
    );
  }
}
