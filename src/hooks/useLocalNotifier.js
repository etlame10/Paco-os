import { useEffect } from 'react'
import { api, isLocalMode } from '../lib/api'
import { getNotificationPrefs } from '../lib/notifications/prefs'
import { inQuietHours } from '../lib/notifications/time'
import { enablePushOnThisDevice, getCurrentSubscription, permissionState } from '../lib/notifications/push'

// - Modo local (sin servidor): muestra los avisos pendientes mientras PACO OS está abierto.
// - Modo Supabase: vuelve a guardar la suscripción push si el navegador la renueva.
export function useNotificationRuntime(settings) {
  useEffect(() => {
    if (!isLocalMode) return
    const tick = async () => {
      const prefs = getNotificationPrefs(settings)
      const now = new Date()
      if (inQuietHours(now, prefs)) return
      const due = (await api.notifications.listUpcoming(50)).filter(
        (n) => n.status === 'pending' && new Date(n.remind_at) <= now,
      )
      for (const n of due) {
        const enabled = prefs.kinds[n.kind] !== false
        if (enabled && permissionState() === 'granted') {
          const reg = await navigator.serviceWorker?.getRegistration()
          const opts = { body: n.body, tag: n.id, data: { url: n.url } }
          if (reg) await reg.showNotification(n.title, opts)
          else new Notification(n.title, opts)
        }
        await api.notifications.update(n.id, {
          status: enabled ? 'sent' : 'skipped',
          sent_at: new Date().toISOString(),
        })
      }
    }
    tick()
    const id = setInterval(tick, 60000)
    return () => clearInterval(id)
  }, [settings])

  useEffect(() => {
    if (isLocalMode || !('serviceWorker' in navigator)) return
    const onMessage = async (e) => {
      if (e.data?.type !== 'pushsubscriptionchange') return
      if (permissionState() === 'granted') enablePushOnThisDevice().catch(() => undefined)
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    // Al abrir la app, si este dispositivo tiene suscripción, se actualiza su "última vez visto".
    getCurrentSubscription()
      .then((sub) => sub && permissionState() === 'granted' && enablePushOnThisDevice())
      .catch(() => undefined)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [])
}
