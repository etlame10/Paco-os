// =====================================================================
// PACO OS — Edge Function "send-notifications"
//
// Envía las notificaciones push de PACO OS mediante el estándar Web Push
// (RFC 8030 + cifrado RFC 8291 + VAPID RFC 8292), usando solo WebCrypto:
// sin dependencias de pago ni servicios externos aparte de los servicios de
// push gratuitos de cada navegador (Google, Apple, Mozilla).
//
// Acciones (POST JSON):
//   { "action": "dispatch" }  -> envía los avisos pendientes de TODOS los usuarios.
//                                Solo Supabase Cron, con la cabecera x-cron-secret.
//   { "action": "test" }      -> aviso de prueba a los dispositivos del usuario
//                                que llama (requiere su sesión de PACO OS).
//
// Secretos (Supabase > Edge Functions > Secrets). NUNCA en GitHub ni en la web:
//   VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT, CRON_SECRET
// SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY los añade Supabase automáticamente.
//
// Al publicarla en el panel: desactiva "Verify JWT" (la función comprueba ella
// misma el token de cron o la sesión del usuario).
// Este archivo es autocontenido para poder pegarlo tal cual en el panel.
// =====================================================================
import { createClient } from 'npm:@supabase/supabase-js@2'

// --- WEBPUSH START (cifrado y firma; probado en scripts/test-webpush.mjs) ---
const te = new TextEncoder()

function b64urlToBytes(s) {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const bin = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(bin, (c) => c.charCodeAt(0))
}

function bytesToB64url(bytes) {
  let bin = ''
  for (const b of new Uint8Array(bytes)) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0))
  let o = 0
  for (const p of parts) {
    out.set(p, o)
    o += p.length
  }
  return out
}

async function hmac(keyBytes, data) {
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, data))
}

// HKDF (RFC 5869) con salida <= 32 bytes
async function hkdf(salt, ikm, info, length) {
  const prk = await hmac(salt, ikm)
  const okm = await hmac(prk, concat(info, new Uint8Array([1])))
  return okm.slice(0, length)
}

// Firma VAPID (JWT ES256) para el servicio de push del endpoint
async function vapidAuthorization(endpoint, vapid) {
  const pub = b64urlToBytes(vapid.publicKey)
  if (pub.length !== 65 || pub[0] !== 4) throw new Error('VAPID_PUBLIC_KEY no válida')
  const jwk = {
    kty: 'EC',
    crv: 'P-256',
    x: bytesToB64url(pub.slice(1, 33)),
    y: bytesToB64url(pub.slice(33, 65)),
    d: vapid.privateKey,
    ext: true,
  }
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign'])
  const header = bytesToB64url(te.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })))
  const claims = bytesToB64url(
    te.encode(
      JSON.stringify({
        aud: new URL(endpoint).origin,
        exp: Math.floor(Date.now() / 1000) + 12 * 3600,
        sub: vapid.subject,
      }),
    ),
  )
  const unsigned = `${header}.${claims}`
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, te.encode(unsigned))
  return `vapid t=${unsigned}.${bytesToB64url(sig)}, k=${vapid.publicKey}`
}

// Cifrado aes128gcm del contenido (RFC 8291)
async function encryptPayload(subscription, plaintext) {
  const uaPublic = b64urlToBytes(subscription.p256dh)
  const authSecret = b64urlToBytes(subscription.auth)
  const asKeys = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits'])
  const asPublic = new Uint8Array(await crypto.subtle.exportKey('raw', asKeys.publicKey))
  const uaKey = await crypto.subtle.importKey('raw', uaPublic, { name: 'ECDH', namedCurve: 'P-256' }, false, [])
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, asKeys.privateKey, 256))

  const ikm = await hkdf(authSecret, shared, concat(te.encode('WebPush: info\0'), uaPublic, asPublic), 32)
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const cek = await hkdf(salt, ikm, te.encode('Content-Encoding: aes128gcm\0'), 16)
  const nonce = await hkdf(salt, ikm, te.encode('Content-Encoding: nonce\0'), 12)

  const key = await crypto.subtle.importKey('raw', cek, { name: 'AES-GCM' }, false, ['encrypt'])
  const record = concat(te.encode(plaintext), new Uint8Array([2])) // 0x02 = último registro
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, record))

  const rs = new Uint8Array([0, 0, 16, 0]) // tamaño de registro 4096
  return concat(salt, rs, new Uint8Array([asPublic.length]), asPublic, cipher)
}

async function sendWebPush(subscription, payload, vapid, { ttl = 86400, urgency = 'normal' } = {}) {
  const body = await encryptPayload(subscription, JSON.stringify(payload))
  const res = await fetch(subscription.endpoint, {
    method: 'POST',
    headers: {
      Authorization: await vapidAuthorization(subscription.endpoint, vapid),
      'Content-Encoding': 'aes128gcm',
      'Content-Type': 'application/octet-stream',
      TTL: String(ttl),
      Urgency: urgency,
    },
    body,
  })
  return { ok: res.ok, status: res.status, text: res.ok ? '' : (await res.text()).slice(0, 300) }
}
// --- WEBPUSH END ---

// ---------------------------------------------------------------------
// Preferencias (mismos valores por defecto que src/lib/notifications/prefs.js)
// ---------------------------------------------------------------------
const DEFAULT_PREFS = {
  kinds: { task: true, exam: true, event: true, custom: true, system: true },
  quietStart: '23:00',
  quietEnd: '08:00',
  timezone: 'Europe/Madrid',
}

function prefsFor(settings) {
  const p = settings?.notifications || {}
  return { ...DEFAULT_PREFS, ...p, kinds: { ...DEFAULT_PREFS.kinds, ...(p.kinds || {}) } }
}

function localMinutes(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone, hourCycle: 'h23', hour: '2-digit', minute: '2-digit' }).formatToParts(date)
  const h = Number(parts.find((p) => p.type === 'hour').value)
  const m = Number(parts.find((p) => p.type === 'minute').value)
  return h * 60 + m
}

function inQuietHours(date, prefs) {
  if (!prefs.quietStart || !prefs.quietEnd || prefs.quietStart === prefs.quietEnd) return false
  const toMin = (s) => Number(s.split(':')[0]) * 60 + Number(s.split(':')[1])
  let now
  try {
    now = localMinutes(date, prefs.timezone)
  } catch {
    now = localMinutes(date, 'Europe/Madrid')
  }
  const start = toMin(prefs.quietStart)
  const end = toMin(prefs.quietEnd)
  return start < end ? now >= start && now < end : now >= start || now < end
}

// ---------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-cron-secret',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })

function env(name) {
  return (Deno.env.get(name) || '').trim()
}

function serviceKey() {
  const legacy = env('SUPABASE_SERVICE_ROLE_KEY')
  if (legacy) return legacy
  // Proyectos con las nuevas claves: SUPABASE_SECRET_KEYS = {"default": "sb_secret_..."}
  try {
    const keys = JSON.parse(env('SUPABASE_SECRET_KEYS') || '{}')
    return keys.default || Object.values(keys)[0] || ''
  } catch {
    return ''
  }
}

function timingSafeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return diff === 0
}

const MAX_ATTEMPTS = 3
const STALE_MS = 24 * 3600 * 1000 // avisos con más de 24 h de retraso se descartan (p. ej. tras una pausa)
const STUCK_MS = 10 * 60 * 1000 // "sending" de más de 10 min (función interrumpida) se reintenta

async function deliverToUser(db, subs, payload, vapid) {
  let sent = 0
  const errors = []
  for (const sub of subs) {
    try {
      const r = await sendWebPush(sub, payload, vapid)
      if (r.ok) {
        sent++
        await db
          .from('push_subscriptions')
          .update({ failure_count: 0, last_success_at: new Date().toISOString() })
          .eq('id', sub.id)
      } else if (r.status === 404 || r.status === 410) {
        // El navegador eliminó la suscripción: se quita el dispositivo.
        await db.from('push_subscriptions').delete().eq('id', sub.id)
        errors.push(`${sub.device_name || 'dispositivo'}: suscripción caducada (eliminada)`)
      } else {
        await db
          .from('push_subscriptions')
          .update({ failure_count: (sub.failure_count || 0) + 1 })
          .eq('id', sub.id)
        errors.push(`${sub.device_name || 'dispositivo'}: HTTP ${r.status} ${r.text}`)
      }
    } catch (e) {
      errors.push(`${sub.device_name || 'dispositivo'}: ${e.message}`)
    }
  }
  return { sent, errors }
}

async function dispatch(db, vapid) {
  const now = new Date()
  const stuckBefore = new Date(now.getTime() - STUCK_MS).toISOString()

  const [pendingRes, stuckRes] = await Promise.all([
    db
      .from('notifications')
      .select('*')
      .eq('status', 'pending')
      .lte('remind_at', now.toISOString())
      .order('remind_at', { ascending: true })
      .limit(200),
    db.from('notifications').select('*').eq('status', 'sending').lt('updated_at', stuckBefore).limit(50),
  ])
  if (pendingRes.error) throw pendingRes.error
  if (stuckRes.error) throw stuckRes.error
  const due = [...(pendingRes.data || []), ...(stuckRes.data || [])]
  if (!due.length) return { processed: 0 }

  const userIds = [...new Set(due.map((n) => n.user_id))]
  const [{ data: settingsRows }, { data: subsRows }] = await Promise.all([
    db.from('user_settings').select('user_id, settings').in('user_id', userIds),
    db.from('push_subscriptions').select('*').in('user_id', userIds),
  ])
  const prefsByUser = new Map(userIds.map((id) => [id, prefsFor(settingsRows?.find((r) => r.user_id === id)?.settings)]))
  const subsByUser = new Map(userIds.map((id) => [id, (subsRows || []).filter((s) => s.user_id === id)]))

  const summary = { processed: 0, sent: 0, skipped: 0, postponed: 0, failed: 0 }

  for (const n of due) {
    const prefs = prefsByUser.get(n.user_id)
    const update = (patch) => db.from('notifications').update(patch).eq('id', n.id)

    if (prefs.kinds[n.kind] === false) {
      await update({ status: 'skipped', last_error: 'Tipo de aviso desactivado' })
      summary.skipped++
      continue
    }
    if (now.getTime() - new Date(n.remind_at).getTime() > STALE_MS) {
      await update({ status: 'skipped', last_error: 'Demasiado atrasado (más de 24 h)' })
      summary.skipped++
      continue
    }
    if (inQuietHours(now, prefs)) {
      summary.postponed++ // se queda pendiente hasta que acaben las horas de silencio
      continue
    }

    // Se "reserva" el aviso para que dos ejecuciones simultáneas no lo envíen dos veces.
    const { data: claimed } = await db
      .from('notifications')
      .update({ status: 'sending', attempts: (n.attempts || 0) + 1 })
      .eq('id', n.id)
      .eq('status', n.status)
      .select('id')
    if (!claimed?.length) continue
    summary.processed++

    const subs = subsByUser.get(n.user_id) || []
    if (!subs.length) {
      // Sin dispositivos: el aviso queda en la bandeja de la campana dentro de PACO OS.
      await update({ status: 'sent', sent_at: now.toISOString(), last_error: 'Sin dispositivos con notificaciones activadas' })
      continue
    }

    const payload = { id: n.id, title: n.title, body: n.body, url: n.url || '', tag: n.id, kind: n.kind, timestamp: Date.parse(n.remind_at) }
    const { sent, errors } = await deliverToUser(db, subs, payload, vapid)
    if (sent > 0) {
      await update({ status: 'sent', sent_at: new Date().toISOString(), last_error: errors.join(' | ') || null })
      summary.sent++
    } else {
      const attempts = (n.attempts || 0) + 1
      await update({ status: attempts >= MAX_ATTEMPTS ? 'failed' : 'pending', last_error: errors.join(' | ').slice(0, 1000) })
      summary.failed++
    }
  }
  return summary
}

async function sendTest(db, userId, vapid) {
  const { data: subs, error } = await db.from('push_subscriptions').select('*').eq('user_id', userId)
  if (error) throw error
  const payload = {
    title: 'PACO OS',
    body: '¡Las notificaciones funcionan! 🎉',
    url: '#/ajustes?seccion=notificaciones',
    tag: 'paco-test',
    kind: 'system',
  }
  const result = subs?.length ? await deliverToUser(db, subs, payload, vapid) : { sent: 0, errors: [] }
  // Queda registrado en la bandeja de la campana
  await db.from('notifications').insert({
    user_id: userId,
    kind: 'system',
    title: payload.title,
    body: payload.body,
    url: payload.url,
    remind_at: new Date().toISOString(),
    status: 'sent',
    sent_at: new Date().toISOString(),
    last_error: result.errors.join(' | ') || null,
  })
  return { sent: result.sent, devices: subs?.length || 0, errors: result.errors }
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })
  if (req.method !== 'POST') return json({ error: 'Método no permitido' }, 405)

  const vapid = { publicKey: env('VAPID_PUBLIC_KEY'), privateKey: env('VAPID_PRIVATE_KEY'), subject: env('VAPID_SUBJECT') }
  const url = env('SUPABASE_URL')
  const key = serviceKey()
  if (!vapid.publicKey || !vapid.privateKey || !vapid.subject) {
    return json({ error: 'Faltan los secretos VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY o VAPID_SUBJECT en la Edge Function.' }, 500)
  }
  if (!url || !key) return json({ error: 'Faltan SUPABASE_URL o la clave de servicio en el entorno de la función.' }, 500)

  const db = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } })
  let body = {}
  try {
    body = await req.json()
  } catch {
    body = {}
  }

  try {
    // 1) Supabase Cron: envío de todos los avisos pendientes
    const cronSecret = env('CRON_SECRET')
    const providedSecret = req.headers.get('x-cron-secret') || ''
    if (providedSecret) {
      if (!cronSecret || !timingSafeEqual(providedSecret, cronSecret)) return json({ error: 'No autorizado' }, 401)
      return json({ ok: true, ...(await dispatch(db, vapid)) })
    }

    // 2) Usuario con sesión: solo puede enviarse un aviso de prueba a sí mismo
    const token = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '')
    const { data: userData, error: userError } = token ? await db.auth.getUser(token) : { data: null, error: true }
    if (userError || !userData?.user) return json({ error: 'Inicia sesión en PACO OS para enviar un aviso de prueba.' }, 401)
    if (body.action !== 'test') return json({ error: 'Acción no permitida' }, 400)
    return json({ ok: true, ...(await sendTest(db, userData.user.id, vapid)) })
  } catch (e) {
    console.error(e)
    return json({ error: e.message || 'Error interno' }, 500)
  }
})
