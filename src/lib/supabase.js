import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Si no hay credenciales, PACO OS arranca en "modo local" (datos en este navegador).
export const isSupabaseConfigured = Boolean(url && anonKey && !url.includes('xxxx'))

export const supabase = isSupabaseConfigured
  ? createClient(url, anonKey, {
      // PKCE: el código de login llega como ?code=... y no choca con las rutas con # (HashRouter)
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' },
    })
  : null

export const STORAGE_BUCKET = 'paco-files'
