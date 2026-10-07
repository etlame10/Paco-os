// Punto único de acceso a datos. El resto de la app SOLO importa `api` desde aquí,
// así que cambiar de backend (Supabase / local / otro futuro) no afecta a los módulos.
import { isSupabaseConfigured } from '../supabase'
import { supabaseBackend } from './supabaseBackend'
import { localBackend } from './localBackend'
import { safeSync } from '../notifications/sync'

const backend = isSupabaseConfigured ? supabaseBackend : localBackend

// Los elementos se envuelven para mantener sus avisos programados sincronizados
// automáticamente, sea cual sea el sitio de la app que los cree o modifique.
const items = {
  ...backend.items,
  async create(item) {
    const row = await backend.items.create(item)
    safeSync(backend, row)
    return row
  },
  async update(id, patch) {
    const row = await backend.items.update(id, patch)
    safeSync(backend, row)
    return row
  },
  async bulkInsert(rows) {
    const out = await backend.items.bulkInsert(rows)
    for (const row of out) await safeSync(backend, row)
    return out
  },
}

export const api = { ...backend, items }
export const rawBackend = backend
export const isLocalMode = backend.mode === 'local'
