import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import DashboardContent from "./DashboardContent";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const isSupabaseConfigured = !!(supabaseUrl && supabaseKey);

  let user = null;

  if (isSupabaseConfigured) {
    try {
      const supabase = await createClient();
      const {
        data: { user: supabaseUser },
      } = await supabase.auth.getUser();
      user = supabaseUser;
    } catch (err) {
      console.error("Failed to get Supabase user:", err);
    }
  } else {
    // Supabase is not configured yet - supply mock user to allow offline development
    user = {
      id: "mock-user-id",
      email: "developer@example.com",
      user_metadata: {
        full_name: "Mock Developer",
        name: "Mock Developer",
      },
    } as any;
  }

  if (!user) {
    redirect("/auth/login");
  }

  return <DashboardContent user={user} />;
}