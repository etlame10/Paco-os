import { createClient } from '@supabase/supabase-js'

// Credenciales SOLO desde variables de entorno (nunca escritas en el código):
//   - En local: archivo .env.local (ignorado por Git, ver .env.example)
//   - En GitHub Pages: secretos del repositorio usados por .github/workflows/deploy.yml
// VITE_SUPABASE_ANON_KEY admite la clave "anon" clásica o la nueva Publishable Key
// (sb_publishable_...). Ambas son públicas por diseño: la seguridad la da RLS.
const url = (import.meta.env.VITE_SUPABASE_URL || '').trim()
const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

function isValidUrl(value) {
  try {
    const u = new URL(value)
    return (u.protocol === 'https:' || u.protocol === 'http:') && !u.hostname.includes('xxxx')
  } catch {
    return false
  }
}

// Si falta cualquiera de las dos variables, PACO OS arranca en "modo local" (datos en este navegador).
export const isSupabaseConfigured = Boolean(anonKey && isValidUrl(url))

if (!isSupabaseConfigured && (url || anonKey)) {
  console.warn(
    '[PACO OS] Configuración de Supabase incompleta o no válida: revisa VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY. Se usará el modo local.',
  )
}

export const supabase = isSupabaseConfigured
  ? createClient(url, anonKey, {
      // PKCE: el código de login llega como ?code=... y no choca con las rutas con # (HashRouter)
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' },
    })
  : null

export const STORAGE_BUCKET = 'paco-files'
