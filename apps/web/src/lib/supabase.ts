"use client";

import { createBrowserClient } from "@supabase/ssr";

// Browser Supabase client (ARCHITECTURE.md section 1). Holds the auth session;
// the access token is forwarded to FastAPI for privileged calls.
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}

export const supabase = createClient();
