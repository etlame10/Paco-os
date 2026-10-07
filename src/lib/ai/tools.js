// Capa de herramientas internas de PACO AI.
//
// La IA nunca toca la base de datos directamente: pide usar una herramienta
// (search_items, create_item...) y es ESTE código, en el navegador del usuario,
// quien valida la petición y la ejecuta con la capa de datos `api`. Así:
//   - Todo pasa por Supabase con la sesión del usuario (RLS: solo sus datos).
//   - Se mantienen avisos y repeticiones (la envoltura de api.items se encarga).
//   - Cada herramienta tiene un tipo (read/create/update/delete) que decide si se
//     ejecuta sola o si el usuario debe confirmarla (ver permissions.js).
//
// Los esquemas que ve el modelo están en la Edge Function (supabase/functions/paco-ai).
// Si añades una herramienta, añádela en ambos sitios (lo comprueba npm run test:ai).
import { CORE_KEYS, defaultForm, formToItem } from '../items.js'

export const TOOL_KINDS = {
  list_modules: 'read',
  search_items: 'read',
  get_item: 'read',
  get_agenda: 'read',
  list_files: 'read',
  create_item: 'create',
  update_item: 'update',
  delete_item: 'delete',
}

// Error de validación: se devuelve al modelo para que corrija la petición.
export class ToolError extends Error {}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/
const DATETIME_RE = /^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d$/
const MAX_LIST = 50
const BODY_PREVIEW = 300
const BODY_FULL = 4000

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

function validDate(s) {
  if (!DATE_RE.test(s)) return false
  const [y, m, d] = s.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d
}

function optDate(v, name) {
  if (v === undefined || v === null || v === '') return undefined
  if (typeof v !== 'string' || !validDate(v)) throw new ToolError(`${name} debe ser una fecha YYYY-MM-DD`)
  return v
}

function clampLimit(v, def = 20) {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? Math.min(Math.floor(n), MAX_LIST) : def
}

const truncate = (s, n) => (typeof s === 'string' && s.length > n ? s.slice(0, n) + '…' : s)

// Vista compacta de un elemento para el modelo (los campos de data con su clave).
function compactItem(item, bodyMax = BODY_PREVIEW) {
  const out = { id: item.id, module: item.module, title: item.title || '' }
  if (item.status) out.status = item.status
  if (item.due_date) out.due_date = item.due_date
  if (item.tags?.length) out.tags = item.tags
  if (item.pinned) out.pinned = true
  if (item.body) out.body = truncate(item.body, bodyMax)
  if (isObj(item.data) && Object.keys(item.data).length) out.fields = item.data
  out.updated_at = item.updated_at
  return out
}

function describeField(f) {
  const d = { key: f.key, label: f.label, type: f.type }
  if (f.required) d.required = true
  if (f.options) d.options = f.options.map((o) => o.value)
  if (f.min !== undefined) d.min = f.min
  if (f.max !== undefined) d.max = f.max
  return d
}

// Valida y normaliza los campos que propone la IA según la definición del módulo.
// partial=true (editar): solo se comprueban los campos enviados.
export function normalizeFields(module, input, { partial = false } = {}) {
  if (!isObj(input)) throw new ToolError('fields debe ser un objeto {clave: valor}')
  const fields = module.fields || []
  const byKey = Object.fromEntries(fields.map((f) => [f.key, f]))
  const out = {}
  for (const [key, raw] of Object.entries(input)) {
    if (key === 'reminder') {
      out.reminder = normalizeReminder(module, raw)
      continue
    }
    const f = byKey[key]
    if (!f) {
      const valid = [...fields.map((x) => x.key), ...(acceptsReminder(module) ? ['reminder'] : [])]
      throw new ToolError(`El módulo "${module.id}" no tiene el campo "${key}". Campos válidos: ${valid.join(', ')}`)
    }
    if (f.readOnly) throw new ToolError(`El campo "${key}" es de solo lectura`)
    out[key] = normalizeValue(f, raw)
  }
  if (!partial) {
    for (const f of fields) {
      if (f.required && (out[f.key] === undefined || out[f.key] === '')) throw new ToolError(`Falta el campo obligatorio "${f.key}"`)
    }
  } else if (out.title === '' && byKey.title?.required) {
    throw new ToolError('El título no puede quedar vacío')
  }
  return out
}

function acceptsReminder(module) {
  return Boolean(module.notifications || (module.showInCalendar && module.fields?.some((f) => f.key === 'due_date')))
}

function normalizeReminder(module, v) {
  if (!acceptsReminder(module)) throw new ToolError(`El módulo "${module.id}" no admite recordatorios`)
  if (v === 'default' || v === 'none') return v
  if (typeof v === 'string' && DATETIME_RE.test(v) && validDate(v.slice(0, 10))) return v
  throw new ToolError('reminder debe ser "default", "none" o una fecha y hora YYYY-MM-DDTHH:MM')
}

function normalizeValue(f, v) {
  const clearing = v === null || v === ''
  if (clearing) {
    if (f.required) throw new ToolError(`El campo "${f.key}" es obligatorio`)
    return f.type === 'tags' ? [] : ''
  }
  switch (f.type) {
    case 'text':
    case 'textarea': {
      if (typeof v !== 'string' && typeof v !== 'number') throw new ToolError(`"${f.key}" debe ser texto`)
      const s = String(v).trim()
      const max = f.type === 'text' ? 300 : 20000
      if (s.length > max) throw new ToolError(`"${f.key}" admite como máximo ${max} caracteres`)
      return s
    }
    case 'number':
    case 'money':
    case 'rating':
    case 'progress': {
      const n = typeof v === 'number' ? v : Number(String(v).replace(',', '.'))
      if (!Number.isFinite(n)) throw new ToolError(`"${f.key}" debe ser un número`)
      const min = f.min ?? (f.type === 'rating' || f.type === 'progress' ? 0 : -Infinity)
      const max = f.max ?? (f.type === 'rating' ? 5 : f.type === 'progress' ? 100 : Infinity)
      if (n < min || n > max) throw new ToolError(`"${f.key}" debe estar entre ${min} y ${max}`)
      return n
    }
    case 'date':
      if (typeof v !== 'string' || !validDate(v)) throw new ToolError(`"${f.key}" debe ser una fecha YYYY-MM-DD`)
      return v
    case 'time':
      if (typeof v !== 'string' || !TIME_RE.test(v)) throw new ToolError(`"${f.key}" debe ser una hora HH:MM`)
      return v
    case 'datetime':
      if (typeof v !== 'string' || !DATETIME_RE.test(v) || !validDate(v.slice(0, 10)))
        throw new ToolError(`"${f.key}" debe ser fecha y hora YYYY-MM-DDTHH:MM`)
      return v
    case 'select': {
      const values = (f.options || []).map((o) => o.value)
      if (!values.includes(v)) throw new ToolError(`"${f.key}" debe ser uno de: ${values.join(', ')}`)
      return v
    }
    case 'checkbox':
      if (typeof v !== 'boolean') throw new ToolError(`"${f.key}" debe ser true o false`)
      return v
    case 'url':
      if (typeof v !== 'string' || !/^https?:\/\/\S+$/i.test(v.trim())) throw new ToolError(`"${f.key}" debe ser un enlace http(s)://`)
      return v.trim()
    case 'tags': {
      const list = Array.isArray(v) ? v : String(v).split(',')
      const tags = [...new Set(list.map((t) => String(t).trim()).filter(Boolean))]
      if (tags.length > 20) throw new ToolError('Como máximo 20 etiquetas')
      return tags.map((t) => t.slice(0, 40))
    }
    default:
      return v
  }
}

// Texto legible de los cambios, para la tarjeta de confirmación.
function describeValues(module, values) {
  const byKey = Object.fromEntries((module.fields || []).map((f) => [f.key, f]))
  return Object.entries(values).map(([k, v]) => {
    if (k === 'reminder') return { label: 'Recordatorio', value: v === 'none' ? 'Sin aviso' : v === 'default' ? 'Por defecto' : v.replace('T', ' ') }
    const f = byKey[k]
    let shown = v
    if (f?.type === 'select') shown = f.options.find((o) => o.value === v)?.label ?? v
    else if (Array.isArray(v)) shown = v.join(', ')
    else if (typeof v === 'boolean') shown = v ? 'Sí' : 'No'
    if (shown === '' || (Array.isArray(v) && !v.length)) shown = '(vacío)'
    return { label: f?.label || k, value: truncate(String(shown), 160) }
  })
}

function applyReminder(row, values, baseData) {
  if (values.reminder === undefined) return row
  const data = { ...(row.data || baseData || {}) }
  if (values.reminder === 'default') delete data.reminder
  else data.reminder = values.reminder
  return { ...row, data }
}

/**
 * Crea la caja de herramientas para una conversación.
 * ctx: { api, modules (módulos activos), getModule }
 * prepare(name, input) valida la petición y devuelve una acción preparada:
 *   { name, kind, title, details: [{label, value}], danger, run(): Promise<resultado> }
 * Lanza ToolError si la petición no es válida (no se pregunta nada al usuario).
 */
export function createToolbox({ api, modules, getModule }) {
  const itemModules = () => modules.filter((m) => m.usesItems !== false)

  const writableModule = (id) => {
    const m = getModule(id)
    if (!m || m.usesItems === false) throw new ToolError(`No existe el módulo "${id}". Usa list_modules para ver los disponibles.`)
    if (!modules.some((x) => x.id === m.id)) throw new ToolError(`El módulo "${m.name}" está desactivado. El usuario puede activarlo en Módulos.`)
    return m
  }

  const fetchItem = async (id) => {
    if (typeof id !== 'string' || !id) throw new ToolError('id es obligatorio')
    let item = null
    try {
      item = await api.items.get(id)
    } catch {
      item = null // id con formato no válido
    }
    if (!item) throw new ToolError(`No existe ningún elemento con id ${id}`)
    return item
  }

  const itemLabel = (item) => {
    const m = getModule(item.module)
    return `${m?.itemName ? m.itemName[0].toUpperCase() + m.itemName.slice(1) : m?.name || item.module}: «${item.title || 'Sin título'}»`
  }

  const handlers = {
    async list_modules() {
      return {
        title: 'Consultar módulos',
        run: async () => ({
          modules: itemModules().map((m) => ({
            id: m.id,
            name: m.name,
            item_name: m.itemName || null,
            description: m.description || '',
            in_calendar: Boolean(m.showInCalendar),
            repeats: m.recurrence ? { done_status: m.recurrence.doneStatus, open_status: m.recurrence.openStatus } : undefined,
            reminders: acceptsReminder(m) || undefined,
            fields: (m.fields || []).map(describeField),
          })),
          note: 'Los campos "title", "body", "status", "due_date" y "tags" son columnas; el resto se guardan como fields del elemento.',
        }),
      }
    },

    async search_items(input) {
      const module = input.module ? writableModuleForRead(input.module) : null
      const from = optDate(input.due_from, 'due_from')
      const to = optDate(input.due_to, 'due_to')
      const text = typeof input.text === 'string' ? input.text.trim().toLowerCase() : ''
      const limit = clampLimit(input.limit)
      return {
        title: 'Buscar elementos',
        run: async () => {
          let rows
          if (module) rows = await api.items.list({ module: module.id })
          else if (from && to) rows = await api.items.listByDateRange(from, to)
          // El texto se busca aquí (también en etiquetas y campos extra, no solo título y notas).
          else rows = await api.items.list()
          const enabled = new Set(itemModules().map((m) => m.id))
          const filtered = rows.filter((i) => {
            if (!enabled.has(i.module)) return false
            if (text) {
              const hay = `${i.title || ''} ${i.body || ''} ${(i.tags || []).join(' ')} ${JSON.stringify(i.data || {})}`.toLowerCase()
              if (!hay.includes(text)) return false
            }
            if (input.status && i.status !== input.status) return false
            if (input.pinned === true && !i.pinned) return false
            if (from && (!i.due_date || i.due_date < from)) return false
            if (to && (!i.due_date || i.due_date > to)) return false
            if (input.include_done === false) {
              const m = getModule(i.module)
              const done = m?.recurrence?.doneStatus
              if (done && i.status === done) return false
            }
            return true
          })
          return { total: filtered.length, items: filtered.slice(0, limit).map((i) => compactItem(i)), truncated: filtered.length > limit || undefined }
        },
      }
    },

    async get_item(input) {
      const item = await fetchItem(input.id)
      return {
        title: 'Leer elemento',
        run: async () => {
          const notifs = await api.notifications.listForItem(item.id).catch(() => [])
          return {
            item: compactItem(item, BODY_FULL),
            reminders: notifs
              .filter((n) => n.status === 'pending' || n.status === 'failed')
              .map((n) => ({ remind_at: n.remind_at, title: n.title })),
          }
        },
      }
    },

    async get_agenda(input) {
      const from = optDate(input.from, 'from')
      const to = optDate(input.to, 'to')
      if (!from || !to) throw new ToolError('from y to son obligatorios (YYYY-MM-DD)')
      if (to < from) throw new ToolError('to debe ser posterior o igual a from')
      return {
        title: 'Consultar agenda',
        run: async () => {
          const rows = await api.items.listByDateRange(from, to)
          const cal = new Set(itemModules().filter((m) => m.showInCalendar).map((m) => m.id))
          const items = rows.filter((i) => cal.has(i.module))
          return { from, to, total: items.length, items: items.slice(0, MAX_LIST).map((i) => compactItem(i, 120)) }
        },
      }
    },

    async list_files(input) {
      const text = typeof input.text === 'string' ? input.text.trim().toLowerCase() : ''
      const limit = clampLimit(input.limit)
      return {
        title: 'Consultar archivos',
        run: async () => {
          const files = (await api.files.list()).filter((f) => !text || `${f.name} ${f.folder || ''}`.toLowerCase().includes(text))
          return {
            total: files.length,
            files: files.slice(0, limit).map((f) => ({ name: f.name, folder: f.folder || '', size: f.size, type: f.mime_type || '', created_at: f.created_at })),
            note: 'Solo se ven nombres y datos de los archivos, no su contenido.',
          }
        },
      }
    },

    async create_item(input) {
      const module = writableModule(input.module)
      const values = normalizeFields(module, input.fields, { partial: false })
      const { reminder, ...plain } = values
      const row = applyReminder(formToItem({ ...defaultForm(module.fields || []), ...plain }), values)
      if (input.pinned === true) row.pinned = true
      return {
        title: `Crear ${module.itemName || 'elemento'} en ${module.name}`,
        module: module.id,
        details: describeValues(module, values),
        run: async () => {
          const created = await api.items.create({ module: module.id, ...row })
          return { ok: true, created: compactItem(created) }
        },
      }
    },

    async update_item(input) {
      const item = await fetchItem(input.id)
      const module = writableModule(item.module)
      const values = input.fields === undefined ? {} : normalizeFields(module, input.fields, { partial: true })
      const hasPin = typeof input.pinned === 'boolean'
      if (!Object.keys(values).length && !hasPin) throw new ToolError('No hay cambios: indica fields o pinned')
      const { reminder, ...plain } = values
      const patch = applyReminder(formToItem(plain, item.data || {}), values, item.data)
      if (!Object.keys(plain).some((k) => !CORE_KEYS.includes(k)) && values.reminder === undefined) delete patch.data
      if (hasPin) patch.pinned = input.pinned
      const details = describeValues(module, values)
      if (hasPin) details.push({ label: 'Fijado', value: input.pinned ? 'Sí' : 'No' })
      return {
        title: `Editar ${itemLabel(item)}`,
        module: item.module,
        details,
        run: async () => {
          const updated = await api.items.update(item.id, patch)
          return { ok: true, updated: compactItem(updated) }
        },
      }
    },

    async delete_item(input) {
      const item = await fetchItem(input.id)
      writableModule(item.module)
      return {
        title: `Eliminar ${itemLabel(item)}`,
        module: item.module,
        details: [
          ...(item.due_date ? [{ label: 'Fecha', value: item.due_date }] : []),
          { label: 'Atención', value: 'Se borrará definitivamente junto con sus avisos.' },
        ],
        danger: true,
        run: async () => {
          await api.items.remove(item.id)
          return { ok: true, deleted: { id: item.id, title: item.title } }
        },
      }
    },
  }

  // Para leer se admite también un módulo desactivado, pero tiene que existir.
  function writableModuleForRead(id) {
    const m = getModule(id)
    if (!m || m.usesItems === false) throw new ToolError(`No existe el módulo "${id}". Usa list_modules para ver los disponibles.`)
    return m
  }

  return {
    async prepare(name, input) {
      const handler = handlers[name]
      if (!handler) throw new ToolError(`Herramienta desconocida: ${name}`)
      const prepared = await handler(isObj(input) ? input : {})
      return { name, kind: TOOL_KINDS[name], details: [], danger: false, ...prepared }
    },
  }
}
