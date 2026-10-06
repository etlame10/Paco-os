import { createClient } from '@supabase/supabase-js'

// Credenciales SOLO desde variables de entorno (nunca escritas en el código):
//   - En local: archivo .env.local (ignorado por Git, ver .env.example)
//   - En GitHub Pages: secretos del repositorio usados por .github/workflows/deploy.yml
// VITE_SUPABASE_ANON_KEY debe ser la Publishable Key (sb_publishable_...) o la clave "anon"
// clásica. Ambas son públicas por diseño: la seguridad la da RLS.
// La Secret Key (sb_secret_...) o "service_role" JAMÁS deben llegar al navegador.
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

// Detecta claves con privilegios de administrador (no deben usarse nunca en el frontend).
function isSecretKey(key) {
  if (key.startsWith('sb_secret_')) return true
  // Claves JWT antiguas: la "service_role" lleva role=service_role en su contenido.
  const parts = key.split('.')
  if (parts.length === 3) {
    try {
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
      return payload?.role === 'service_role'
    } catch {
      return false
    }
  }
  return false
}

const secretKeyDetected = Boolean(anonKey) && isSecretKey(anonKey)

// Mensaje visible en la pantalla de login si la configuración es peligrosa.
export const supabaseConfigError = secretKeyDetected
  ? 'PACO OS se ha construido con una clave SECRETA de Supabase y se ha bloqueado por seguridad. ' +
    'En GitHub (Settings → Secrets and variables → Actions) pon en VITE_SUPABASE_ANON_KEY la Publishable key ' +
    '(sb_publishable_...), revoca la Secret key en Supabase y vuelve a desplegar.'
  : null

// Si falta cualquiera de las dos variables, PACO OS arranca en "modo local" (datos en este navegador).
// Si la clave es secreta, NO se crea el cliente de Supabase.
export const isSupabaseConfigured = Boolean(anonKey && isValidUrl(url) && !secretKeyDetected)

if (secretKeyDetected) {
  console.error('[PACO OS] ' + supabaseConfigError)
} else if (!isSupabaseConfigured && (url || anonKey)) {
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
