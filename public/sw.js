/* PACO OS — Service worker
 * - Recibe las notificaciones push (enviadas por la Edge Function "send-notifications")
 * - Al tocar una notificación abre (o enfoca) PACO OS en el elemento correspondiente
 * No cachea la app: GitHub Pages sirve siempre la última versión publicada.
 */
const VERSION = 'paco-sw-1'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { title: 'PACO OS', body: event.data ? event.data.text() : '' }
  }
  const scope = self.registration.scope
  const title = data.title || 'PACO OS'
  const options = {
    body: data.body || '',
    icon: scope + 'icons/icon-192.png',
    badge: scope + 'icons/badge-72.png',
    tag: data.tag || undefined,
    renotify: Boolean(data.tag),
    timestamp: data.timestamp || Date.now(),
    data: { url: data.url || '', id: data.id || null, version: VERSION },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const scope = self.registration.scope
  const rel = event.notification.data?.url || ''
  const target = rel.startsWith('http') ? rel : scope + rel.replace(/^\.?\//, '')

  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const existing = windows.find((w) => w.url.startsWith(scope))
      if (existing) {
        await existing.focus()
        if ('navigate' in existing) return existing.navigate(target).catch(() => undefined)
        return undefined
      }
      return self.clients.openWindow(target)
    })(),
  )
})

// El navegador puede renovar la suscripción: se avisa a la app abierta para que la vuelva a guardar.
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) =>
      clients.forEach((c) => c.postMessage({ type: 'pushsubscriptionchange' })),
    ),
  )
})
