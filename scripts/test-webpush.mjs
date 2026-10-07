// Prueba del cifrado Web Push de la Edge Function (supabase/functions/send-notifications).
// Extrae el bloque WEBPUSH de index.ts y comprueba, con librerías de referencia, que:
//   1. un navegador podría descifrar el mensaje (RFC 8291, aes128gcm) -> http_ece
//   2. la firma VAPID (JWT ES256) es válida para la clave pública       -> jose
// Uso: npm run test:push
import { readFileSync } from 'node:fs'
import crypto from 'node:crypto'
import webpush from 'web-push'
import ece from 'http_ece'
import { importJWK, jwtVerify } from 'jose'

const src = readFileSync(new URL('../supabase/functions/send-notifications/index.ts', import.meta.url), 'utf8')
const block = src.split('// --- WEBPUSH START')[1].split('// --- WEBPUSH END')[0].replace(/^.*\n/, '')
const { encryptPayload, vapidAuthorization } = new Function(
  `${block}; return { encryptPayload, vapidAuthorization }`,
)()

let failures = 0
const ok = (cond, msg) => {
  console.log(`${cond ? '✔' : '✘'} ${msg}`)
  if (!cond) failures++
}

// --- 1. Cifrado: el "navegador" (ua) descifra lo que envía el servidor ---
const ua = crypto.createECDH('prime256v1')
ua.generateKeys()
const authSecret = crypto.randomBytes(16)
const subscription = {
  endpoint: 'https://fcm.googleapis.com/fcm/send/prueba',
  p256dh: ua.getPublicKey('base64url'),
  auth: authSecret.toString('base64url'),
}
const message = JSON.stringify({ title: 'Examen: Matemáticas II', body: 'Es mañana — ñáéíóú 🎓', url: '#/m/estudios?item=1' })
const body = await encryptPayload(subscription, message)
const decrypted = ece.decrypt(Buffer.from(body), { version: 'aes128gcm', privateKey: ua, authSecret })
ok(decrypted.toString('utf8') === message, 'El contenido cifrado se descifra correctamente (aes128gcm)')
ok(body.length < 4096, `Tamaño del mensaje dentro del límite (${body.length} bytes)`)

// --- 2. VAPID: claves con el mismo formato que "npx web-push generate-vapid-keys" ---
const keys = webpush.generateVAPIDKeys()
const vapid = { publicKey: keys.publicKey, privateKey: keys.privateKey, subject: 'mailto:prueba@example.com' }
const header = await vapidAuthorization(subscription.endpoint, vapid)
const m = header.match(/^vapid t=([^,]+), k=(.+)$/)
ok(Boolean(m) && m[2] === keys.publicKey, 'Cabecera Authorization con formato "vapid t=…, k=…"')
const pub = Buffer.from(keys.publicKey, 'base64url')
const jwk = { kty: 'EC', crv: 'P-256', x: pub.subarray(1, 33).toString('base64url'), y: pub.subarray(33).toString('base64url') }
const { payload } = await jwtVerify(m[1], await importJWK(jwk, 'ES256'))
ok(payload.aud === 'https://fcm.googleapis.com', 'JWT VAPID: audiencia = origen del servicio de push')
ok(payload.sub === vapid.subject && payload.exp > Date.now() / 1000, 'JWT VAPID: firma ES256 válida, sub y caducidad correctos')

// --- 3. Comparación con la librería de referencia web-push (mismo formato de cabeceras) ---
const ref = webpush.generateRequestDetails(
  { endpoint: subscription.endpoint, keys: { p256dh: subscription.p256dh, auth: subscription.auth } },
  message,
  {
  vapidDetails: vapid,
    contentEncoding: 'aes128gcm',
  },
)
ok(ref.headers['Content-Encoding'] === 'aes128gcm', 'Mismo Content-Encoding que la librería web-push')

if (failures) {
  console.error(`\n${failures} comprobación(es) fallida(s)`)
  process.exit(1)
}
console.log('\nWeb Push OK')
