import { createClient, SupabaseClient } from "@supabase/supabase-js";

const url = (import.meta.env?.VITE_SUPABASE_URL as string | undefined)?.trim();
const anonKey = (import.meta.env?.VITE_SUPABASE_ANON_KEY as string | undefined)?.trim();

export const googleAuthEnabled = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = googleAuthEnabled
  ? createClient(url!, anonKey!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;