// Backend local: guarda todo en este navegador (localStorage + IndexedDB).
// Se usa automáticamente cuando Supabase no está configurado, para poder
// probar PACO OS sin cuenta. Tiene exactamente la misma interfaz que supabaseBackend.

const KEY_ITEMS = 'pacoos.items'
const KEY_FILES = 'pacoos.files'
const KEY_SETTINGS = 'pacoos.settings'
const LOCAL_USER = { id: 'local-user', email: 'modo-local@paco.os' }
const LOCAL_SESSION = { user: LOCAL_USER }

const read = (k, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(k)) ?? fallback
  } catch {
    return fallback
  }
}
const write = (k, v) => localStorage.setItem(k, JSON.stringify(v))
const now = () => new Date().toISOString()

// --- IndexedDB para el contenido de los archivos ---
function idb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('pacoos-files', 1)
    req.onupgradeneeded = () => req.result.createObjectStore('blobs')
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}
async function blobOp(mode, fn) {
  const db = await idb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('blobs', mode)
    const req = fn(tx.objectStore('blobs'))
    tx.oncomplete = () => resolve(req?.result)
    tx.onerror = () => reject(tx.error)
  })
}

const sortBy = (arr, key, ascending) =>
  [...arr].sort((a, b) => {
    const x = a[key] ?? ''
    const y = b[key] ?? ''
    return (x < y ? -1 : x > y ? 1 : 0) * (ascending ? 1 : -1)
  })

let listeners = []

export const localBackend = {
  mode: 'local',

  auth: {
    async getSession() {
      return read('pacoos.signedOut', false) ? null : LOCAL_SESSION
    },
    onChange(cb) {
      listeners.push(cb)
      return () => (listeners = listeners.filter((l) => l !== cb))
    },
    async signIn() {
      write('pacoos.signedOut', false)
      listeners.forEach((l) => l(LOCAL_SESSION, 'SIGNED_IN'))
    },
    async signUp() {
      return this.signIn()
    },
    async magicLink() {
      return this.signIn()
    },
    async resetPassword() {},
    async updatePassword() {},
    async signOut() {
      write('pacoos.signedOut', true)
      listeners.forEach((l) => l(null, 'SIGNED_OUT'))
    },
  },

  items: {
    async list({ module, orderBy = 'created_at', ascending = false } = {}) {
      const all = read(KEY_ITEMS, [])
      return sortBy(module ? all.filter((i) => i.module === module) : all, orderBy, ascending)
    },
    async listByDateRange(from, to) {
      const all = read(KEY_ITEMS, []).filter((i) => i.due_date && i.due_date >= from && i.due_date <= to)
      return sortBy(all, 'due_date', true)
    },
    async listPinned() {
      return sortBy(read(KEY_ITEMS, []).filter((i) => i.pinned), 'updated_at', false)
    },
    async listRecent(limit = 10) {
      return sortBy(read(KEY_ITEMS, []), 'updated_at', false).slice(0, limit)
    },
    async search(text, limit = 30) {
      const t = text.toLowerCase().trim()
      if (!t) return []
      return sortBy(
        read(KEY_ITEMS, []).filter(
          (i) => i.title.toLowerCase().includes(t) || (i.body || '').toLowerCase().includes(t),
        ),
        'updated_at',
        false,
      ).slice(0, limit)
    },
    async create(item) {
      const all = read(KEY_ITEMS, [])
      const row = {
        id: crypto.randomUUID(),
        user_id: LOCAL_USER.id,
        title: '',
        body: '',
        status: null,
        due_date: null,
        tags: [],
        data: {},
        pinned: false,
        position: 0,
        ...item,
        created_at: now(),
        updated_at: now(),
      }
      write(KEY_ITEMS, [row, ...all])
      return row
    },
    async update(id, patch) {
      let updated
      write(
        KEY_ITEMS,
        read(KEY_ITEMS, []).map((i) => (i.id === id ? (updated = { ...i, ...patch, updated_at: now() }) : i)),
      )
      return updated
    },
    async remove(id) {
      write(KEY_ITEMS, read(KEY_ITEMS, []).filter((i) => i.id !== id))
    },
    async bulkInsert(items) {
      const out = []
      for (const it of items) out.push(await this.create(it))
      return out
    },
  },

  files: {
    async list() {
      return sortBy(read(KEY_FILES, []), 'created_at', false)
    },
    async upload(file, folder = '') {
      const row = {
        id: crypto.randomUUID(),
        user_id: LOCAL_USER.id,
        name: file.name,
        path: `local/${crypto.randomUUID()}`,
        folder,
        size: file.size,
        mime_type: file.type || null,
        created_at: now(),
      }
      await blobOp('readwrite', (s) => s.put(file, row.path))
      write(KEY_FILES, [row, ...read(KEY_FILES, [])])
      return row
    },
    async getUrl(file) {
      const blob = await blobOp('readonly', (s) => s.get(file.path))
      if (!blob) throw new Error('Archivo no encontrado en este navegador')
      return URL.createObjectURL(blob)
    },
    async update(id, patch) {
      let updated
      write(
        KEY_FILES,
        read(KEY_FILES, []).map((f) => (f.id === id ? (updated = { ...f, ...patch }) : f)),
      )
      return updated
    },
    async remove(file) {
      await blobOp('readwrite', (s) => s.delete(file.path))
      write(KEY_FILES, read(KEY_FILES, []).filter((f) => f.id !== file.id))
    },
  },

  settings: {
    async get() {
      return read(KEY_SETTINGS, null)
    },
    async save(settings) {
      write(KEY_SETTINGS, settings)
    },
  },
}
