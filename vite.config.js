import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// ---------------------------------------------------------------------
// Variables de Supabase en local (.env.local)
// Vite solo entiende archivos .env en UTF-8. En Windows es fácil acabar con un
// .env.local en UTF-16 (PowerShell: `echo ... > .env.local`) o llamado
// ".env.local.txt" (Bloc de notas). En esos casos PACO OS arrancaba en "modo local"
// sin decir por qué. Aquí se rescatan esos casos y se avisa en la terminal.
// Solo se leen las variables públicas VITE_* (nunca claves secretas).
// ---------------------------------------------------------------------
const KEYS = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY', 'VITE_VAPID_PUBLIC_KEY']
const CANDIDATES = ['.env.local', '.env', '.env.development.local', '.env.development', '.env.local.txt', '.env.txt', 'env.local', 'env.local.txt']

function decode(buf) {
  if (buf[0] === 0xff && buf[1] === 0xfe) return { text: buf.subarray(2).toString('utf16le'), encoding: 'UTF-16' }
  if (buf[0] === 0xfe && buf[1] === 0xff) return { text: Buffer.from(buf.subarray(2)).swap16().toString('utf16le'), encoding: 'UTF-16' }
  // UTF-16 sin marca: muchos bytes nulos
  const nulls = buf.subarray(0, 200).filter((b) => b === 0).length
  if (nulls > 20) return { text: buf.toString('utf16le'), encoding: 'UTF-16' }
  return { text: buf.toString('utf8').replace(/^﻿/, ''), encoding: 'UTF-8' }
}

function parse(text) {
  const out = {}
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)\s*$/)
    if (!m || !KEYS.includes(m[1])) continue
    const v = m[2].replace(/\s+#.*$/, '').replace(/^(['"])(.*)\1$/, '$2').trim()
    if (v) out[m[1]] = v
  }
  return out
}

function prepareEnv(mode, root) {
  const env = loadEnv(mode, root, 'VITE_')
  const notes = []
  for (const name of CANDIDATES) {
    const file = path.join(root, name)
    if (!fs.existsSync(file)) continue
    const { text, encoding } = decode(fs.readFileSync(file))
    const values = parse(text)
    const official = ['.env.local', '.env', '.env.development.local', '.env.development'].includes(name)
    for (const [k, v] of Object.entries(values)) {
      if (env[k] || process.env[k]) continue
      process.env[k] = v // Vite usa las variables VITE_* de process.env
      env[k] = v
      if (!official) notes.push(`se ha leído ${k} de "${name}": cambia el nombre del archivo a ".env.local"`)
      else if (encoding !== 'UTF-8') notes.push(`"${name}" está guardado en ${encoding}: guárdalo como UTF-8`)
    }
  }
  return { env, notes: [...new Set(notes)] }
}

// base './' -> rutas relativas: funciona en GitHub Pages (usuario.github.io/repo/)
// y en cualquier otro hosting estático sin tocar nada.
export default defineConfig(({ command, mode }) => {
  const root = process.cwd()
  const { env, notes } = prepareEnv(mode, root)
  if (command === 'serve') {
    const missing = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY'].filter((k) => !env[k])
    if (missing.length) {
      console.warn(
        `\n[PACO OS] MODO LOCAL: falta ${missing.join(' y ')}.` +
          `\n          Crea ".env.local" en ${root} (copia .env.example), rellena los valores y reinicia npm run dev.` +
          '\n          Sin Supabase, PACO AI no está disponible.\n',
      )
    } else {
      let host = env.VITE_SUPABASE_URL
      try {
        host = new URL(env.VITE_SUPABASE_URL).host
      } catch {
        /* se avisa en el navegador */
      }
      console.info(`\n[PACO OS] Supabase: ${host} (PACO AI usará la Edge Function "paco-ai")\n`)
    }
    for (const n of notes) console.warn(`[PACO OS] Aviso: ${n}`)
  }
  return {
    plugins: [react()],
    base: './',
  }
})
