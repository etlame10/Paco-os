// Punto único de acceso a datos. El resto de la app SOLO importa `api` desde aquí,
// así que cambiar de backend (Supabase / local / otro futuro) no afecta a los módulos.
import { isSupabaseConfigured } from '../supabase'
import { supabaseBackend } from './supabaseBackend'
import { localBackend } from './localBackend'

export const api = isSupabaseConfigured ? supabaseBackend : localBackend
export const isLocalMode = api.mode === 'local'
