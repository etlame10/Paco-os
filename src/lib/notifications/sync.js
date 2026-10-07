// Mantiene la tabla de avisos sincronizada con los elementos de los módulos.
// Se llama automáticamente desde la capa de datos (src/lib/api/index.js) cada vez
// que se crea o modifica un elemento, venga de donde venga (formulario, captura
// rápida, calendario, importación...). Al borrar un elemento, sus avisos se borran
// solos (ON DELETE CASCADE en Supabase; a mano en el modo local).
import { computeItemNotifications } from './rules'
import { getNotificationPrefs } from './prefs'

// La capa de datos no conoce React: SettingsContext le pasa aquí los módulos y ajustes actuales.
let context = { getModule: () => null, settings: null }
export function setNotificationContext(ctx) {
  context = ctx
}

const OPEN = ['pending', 'failed']

export async function syncItemNotifications(backend, item) {
  if (!item?.id || !backend.notifications) return
  const module = context.getModule(item.module)
  const prefs = getNotificationPrefs(context.settings)
  const desired = module ? computeItemNotifications(item, module, prefs) : []
  const existing = await backend.notifications.listForItem(item.id)

  const byKey = new Map(existing.map((n) => [n.dedupe_key, n]))
  for (const d of desired) {
    const cur = byKey.get(d.dedupe_key)
    byKey.delete(d.dedupe_key)
    if (!cur) {
      await backend.notifications.create({ ...d, item_id: item.id, status: 'pending' })
    } else if (
      cur.remind_at !== d.remind_at &&
      new Date(cur.remind_at).getTime() !== new Date(d.remind_at).getTime()
    ) {
      // Nueva fecha/hora: se vuelve a programar (aunque ya se hubiera enviado el anterior).
      await backend.notifications.update(cur.id, {
        ...d,
        status: 'pending',
        attempts: 0,
        last_error: null,
        sent_at: null,
        read_at: null,
      })
    } else if (cur.title !== d.title || cur.body !== d.body || (OPEN.includes(cur.status) && cur.kind !== d.kind)) {
      await backend.notifications.update(cur.id, { title: d.title, body: d.body, kind: d.kind, url: d.url })
    }
  }
  // Avisos que ya no corresponden (tarea completada, fecha quitada, "sin aviso"...):
  // se eliminan solo los que aún no se habían enviado; los enviados quedan como historial.
  for (const old of byKey.values()) {
    if (OPEN.includes(old.status) || old.status === 'sending') await backend.notifications.remove(old.id)
  }
}

export function safeSync(backend, item) {
  return syncItemNotifications(backend, item).catch((e) => console.warn('[PACO OS] No se pudo sincronizar el aviso', e))
}

// Recalcula todos los avisos futuros (por ejemplo, al cambiar la hora por defecto).
export async function resyncAllNotifications(backend) {
  // Si la tabla de avisos aún no existe (schema.sql sin actualizar), falla aquí y se
  // reintentará en el próximo arranque en vez de darse por hecho.
  await backend.notifications.listUpcoming(1)
  const items = await backend.items.list()
  const today = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  for (const item of items) {
    const hasCustom = item.data?.reminder && item.data.reminder !== 'default'
    if ((item.due_date && item.due_date >= today) || hasCustom) await safeSync(backend, item)
  }
}
