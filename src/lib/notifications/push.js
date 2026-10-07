// Web Push en el navegador: service worker, permisos y suscripción del dispositivo.
// La clave PÚBLICA VAPID llega por variable de entorno (VITE_VAPID_PUBLIC_KEY).
// La clave PRIVADA solo existe como secreto de la Edge Function en Supabase.
import { api } from '../api'

export const VAPID_PUBLIC_KEY = (import.meta.env.VITE_VAPID_PUBLIC_KEY || '').trim()

export const isPushConfigured = /^B[A-Za-z0-9_-]{86}$/.test(VAPID_PUBLIC_KEY)

export function isIOS() {
  const ua = navigator.userAgent || ''
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
}

export function isStandalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true
}

export function isPushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export function permissionState() {
  return 'Notification' in window ? Notification.permission : 'unsupported'
}

export function deviceName() {
  const ua = navigator.userAgent || ''
  const os = isIOS()
    ? /iPad/.test(ua) || navigator.maxTouchPoints > 1 ? 'iPad' : 'iPhone'
    : /Android/.test(ua)
      ? 'Android'
      : /Windows/.test(ua)
        ? 'Windows'
        : /Mac OS X/.test(ua)
          ? 'Mac'
          : /Linux/.test(ua)
            ? 'Linux'
            : 'Dispositivo'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Firefox\//.test(ua)
      ? 'Firefox'
      : /Chrome\//.test(ua) && !/Edg\//.test(ua)
        ? 'Chrome'
        : /Safari\//.test(ua)
          ? 'Safari'
          : 'Navegador'
  return `${os} · ${browser}${isStandalone() ? ' (app)' : ''}`
}

// Registro del service worker (también lo hace main.jsx al arrancar).
export async function getRegistration() {
  if (!('serviceWorker' in navigator)) return null
  const existing = await navigator.serviceWorker.getRegistration()
  if (existing) return existing
  return navigator.serviceWorker.register('./sw.js')
}

function urlBase64ToUint8Array(base64) {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(padded)
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

function keyToBase64Url(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

export async function getCurrentSubscription() {
  if (!isPushSupported()) return null
  const reg = await navigator.serviceWorker.getRegistration()
  return reg ? reg.pushManager.getSubscription() : null
}

// Debe llamarse desde un clic del usuario (obligatorio en iOS).
export async function enablePushOnThisDevice() {
  if (!api.push.available) throw new Error('Las notificaciones push necesitan Supabase configurado.')
  if (!isPushConfigured) throw new Error('Falta la clave pública VAPID (VITE_VAPID_PUBLIC_KEY). Ver docs/NOTIFICACIONES.md.')
  if (!isPushSupported()) {
    throw new Error(
      isIOS() && !isStandalone()
        ? 'En iPhone/iPad primero añade PACO OS a la pantalla de inicio y ábrelo desde allí.'
        : 'Este navegador no admite notificaciones push.',
    )
  }
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Has denegado el permiso de notificaciones para PACO OS.')

  const reg = await getRegistration()
  await navigator.serviceWorker.ready
  const key = urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
  let sub = await reg.pushManager.getSubscription()
  // Si la suscripción existente se hizo con otra clave VAPID, se renueva.
  const current = sub?.options?.applicationServerKey
  if (sub && current && keyToBase64Url(current) !== VAPID_PUBLIC_KEY) {
    await sub.unsubscribe()
    sub = null
  }
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })

  const json = sub.toJSON()
  return api.push.saveSubscription({
    endpoint: json.endpoint,
    p256dh: json.keys.p256dh,
    auth: json.keys.auth,
    device_name: deviceName(),
    user_agent: navigator.userAgent.slice(0, 300),
  })
}

export async function disablePushOnThisDevice() {
  const sub = await getCurrentSubscription()
  if (!sub) return
  await api.push.removeByEndpoint(sub.endpoint)
  await sub.unsubscribe()
}
