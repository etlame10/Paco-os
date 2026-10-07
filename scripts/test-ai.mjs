// Pruebas de PACO AI: herramientas internas, permisos y bucle del agente
// (con un modelo simulado: no llama a ninguna API ni gasta nada).
// Uso: npm run test:ai
import { readFileSync } from 'node:fs'
import { TOOL_KINDS, ToolError, createToolbox } from '../src/lib/ai/tools.js'
import { getAiPermissions, policyFor } from '../src/lib/ai/permissions.js'
import { MAX_STEPS, MAX_WRITES_PER_TURN, buildUserMessage, runAgent } from '../src/lib/ai/agent.js'

let fail = 0
let count = 0
const ok = (cond, msg, extra) => {
  count++
  console.log(`${cond ? '✔' : '✘'} ${msg}`)
  if (!cond) {
    fail++
    if (extra !== undefined) console.log('   ', JSON.stringify(extra))
  }
}
const throwsTool = async (fn, re, msg) => {
  try {
    await fn()
    ok(false, msg + ' (no lanzó error)')
  } catch (e) {
    ok(e instanceof ToolError && re.test(e.message), msg, e.message)
  }
}

// ---------- Datos y módulos simulados ----------
const MODULES = [
  {
    id: 'tareas', name: 'Tareas', itemName: 'tarea', showInCalendar: true,
    recurrence: { doneStatus: 'hecha', openStatus: 'pendiente' },
    notifications: { kind: 'task' },
    fields: [
      { key: 'title', label: 'Tarea', type: 'text', required: true },
      { key: 'priority', label: 'Prioridad', type: 'select', default: 'media', options: [{ value: 'alta', label: 'Alta' }, { value: 'media', label: 'Media' }, { value: 'baja', label: 'Baja' }] },
      { key: 'due_date', label: 'Fecha límite', type: 'date' },
      { key: 'status', label: 'Estado', type: 'select', default: 'pendiente', options: [{ value: 'pendiente', label: 'Pendiente' }, { value: 'hecha', label: 'Hecha' }] },
      { key: 'tags', label: 'Etiquetas', type: 'tags' },
      { key: 'body', label: 'Notas', type: 'textarea' },
    ],
  },
  {
    id: 'avisos', name: 'Avisos', itemName: 'aviso', showInCalendar: true,
    fields: [
      { key: 'title', label: 'Aviso', type: 'text', required: true },
      { key: 'due_date', label: 'Día', type: 'date' },
      { key: 'hora', label: 'Hora', type: 'time' },
    ],
  },
  { id: 'notas', name: 'Notas', itemName: 'nota', fields: [{ key: 'title', label: 'Título', type: 'text', required: true }, { key: 'body', label: 'Texto', type: 'textarea' }, { key: 'puntuacion', label: 'Puntuación', type: 'rating' }] },
  { id: 'archivos', name: 'Archivos', usesItems: false, fields: [] },
]
const DISABLED = { id: 'peliculas', name: 'Películas', fields: [{ key: 'title', label: 'Título', type: 'text', required: true }] }
const ALL = [...MODULES, DISABLED]
const getModule = (id) => ALL.find((m) => m.id === id)

function fakeApi(seed = []) {
  let items = seed.map((i) => ({ data: {}, tags: [], updated_at: '2026-10-01T10:00:00Z', ...i }))
  let n = 100
  const calls = []
  return {
    calls,
    get items_() {
      return items
    },
    items: {
      async get(id) {
        return items.find((i) => i.id === id) ?? null
      },
      async list({ module } = {}) {
        return module ? items.filter((i) => i.module === module) : [...items]
      },
      async listByDateRange(from, to) {
        return items.filter((i) => i.due_date && i.due_date >= from && i.due_date <= to)
      },
      async search(t) {
        return items.filter((i) => `${i.title} ${i.body || ''}`.toLowerCase().includes(t.toLowerCase()))
      },
      async create(row) {
        calls.push(['create', row])
        const it = { id: `id${++n}`, updated_at: '2026-10-07T10:00:00Z', tags: [], data: {}, ...row }
        items.push(it)
        return it
      },
      async update(id, patch) {
        calls.push(['update', id, patch])
        items = items.map((i) => (i.id === id ? { ...i, ...patch } : i))
        return items.find((i) => i.id === id)
      },
      async remove(id) {
        calls.push(['remove', id])
        items = items.filter((i) => i.id !== id)
      },
    },
    notifications: { async listForItem() { return [{ status: 'pending', remind_at: '2026-10-08T07:00:00Z', title: 'Tarea: X' }] } },
    files: { async list() { return [{ name: 'contrato.pdf', folder: 'casa', size: 1000, mime_type: 'application/pdf', created_at: '2026-10-01' }, { name: 'foto.jpg', size: 5 }] } },
  }
}

const SEED = [
  { id: 't1', module: 'tareas', title: 'Llamar al banco', status: 'pendiente', due_date: '2026-10-08', data: { priority: 'alta', repeat: 'weekly' } },
  { id: 't2', module: 'tareas', title: 'Comprar pan', status: 'hecha', due_date: '2026-10-07', data: { priority: 'baja' } },
  { id: 'a1', module: 'avisos', title: 'Gimnasio', due_date: '2026-10-09', data: { hora: '18:00' } },
  { id: 'n1', module: 'notas', title: 'Ideas viaje', body: 'Ir a Lisboa en primavera', data: {} },
  { id: 'p1', module: 'peliculas', title: 'Dune', data: {} },
]

const toolbox = (api) => createToolbox({ api, modules: MODULES, getModule })

// ---------- Paridad con la Edge Function ----------
{
  const src = readFileSync(new URL('../supabase/functions/paco-ai/index.ts', import.meta.url), 'utf8')
  const block = src.slice(src.indexOf('PACO_AI TOOLS START'), src.indexOf('PACO_AI TOOLS END'))
  const names = [...block.matchAll(/name: '([a-z_]+)'/g)].map((m) => m[1]).sort()
  ok(JSON.stringify(names) === JSON.stringify(Object.keys(TOOL_KINDS).sort()), 'las herramientas de la Edge Function coinciden con las del navegador', names)
  ok(!/sk-ant-[\w-]{8}|sb_secret_\w{8}|eyJhbGci/.test(src), 'la Edge Function no contiene claves')
}

// ---------- Herramientas: validación ----------
{
  const api = fakeApi(SEED)
  const tb = toolbox(api)
  const a = await tb.prepare('create_item', { module: 'tareas', fields: { title: 'Pagar luz', due_date: '2026-10-10', priority: 'alta', tags: 'casa, facturas' } })
  ok(a.kind === 'create' && a.title === 'Crear tarea en Tareas' && a.module === 'tareas', 'create_item prepara una acción de tipo create', a.title)
  ok(a.details.some((d) => d.label === 'Prioridad' && d.value === 'Alta'), 'los detalles muestran etiquetas legibles', a.details)
  ok(api.calls.length === 0, 'preparar NO modifica nada')
  const r = await a.run()
  const row = api.calls[0][1]
  ok(r.ok && row.status === 'pendiente' && row.data.priority === 'alta' && row.due_date === '2026-10-10', 'al ejecutar crea con valores por defecto y campos en data', row)
  ok(JSON.stringify(row.tags) === '["casa","facturas"]', 'etiquetas normalizadas', row.tags)

  await throwsTool(() => tb.prepare('create_item', { module: 'tareas', fields: { title: 'X', priority: 'urgente' } }), /alta, media, baja/, 'select con valor no válido -> error con opciones')
  await throwsTool(() => tb.prepare('create_item', { module: 'tareas', fields: { title: 'X', color: 'rojo' } }), /no tiene el campo "color"/, 'campo desconocido -> error')
  await throwsTool(() => tb.prepare('create_item', { module: 'tareas', fields: { priority: 'alta' } }), /obligatorio "title"/, 'falta el título -> error')
  await throwsTool(() => tb.prepare('create_item', { module: 'tareas', fields: { title: 'X', due_date: '2026-02-30' } }), /YYYY-MM-DD/, 'fecha imposible -> error')
  await throwsTool(() => tb.prepare('create_item', { module: 'avisos', fields: { title: 'X', hora: '25:00' } }), /HH:MM/, 'hora no válida -> error')
  await throwsTool(() => tb.prepare('create_item', { module: 'peliculas', fields: { title: 'X' } }), /desactivado/, 'módulo desactivado -> no se puede escribir')
  await throwsTool(() => tb.prepare('create_item', { module: 'archivos', fields: { title: 'X' } }), /No existe el módulo/, 'Archivos no admite elementos')
  await throwsTool(() => tb.prepare('create_item', { module: 'notas', fields: { title: 'X', puntuacion: 9 } }), /entre 0 y 5/, 'puntuación fuera de rango -> error')
  await throwsTool(() => tb.prepare('create_item', { module: 'notas', fields: { title: 'X', reminder: 'none' } }), /no admite recordatorios/, 'recordatorio en módulo sin avisos -> error')
  await throwsTool(() => tb.prepare('borrar_todo', {}), /desconocida/, 'herramienta inexistente -> error')
  await throwsTool(() => tb.prepare('update_item', { id: 'nope', fields: { title: 'x' } }), /No existe ningún elemento/, 'editar un id inexistente -> error')
  await throwsTool(() => tb.prepare('update_item', { id: 't1' }), /No hay cambios/, 'editar sin cambios -> error')
  await throwsTool(() => tb.prepare('update_item', { id: 't1', fields: { title: '' } }), /no puede quedar vacío|obligatorio/, 'no se puede vaciar el título')
}

// ---------- Herramientas: editar, borrar, recordatorios ----------
{
  const api = fakeApi(SEED)
  const tb = toolbox(api)
  await (await tb.prepare('update_item', { id: 't1', fields: { status: 'hecha' } })).run()
  ok(api.calls[0][2].status === 'hecha' && !('data' in api.calls[0][2]), 'completar solo envía status (no reescribe data)', api.calls[0][2])

  await (await tb.prepare('update_item', { id: 't1', fields: { priority: 'baja' } })).run()
  ok(api.calls[1][2].data.priority === 'baja' && api.calls[1][2].data.repeat === 'weekly', 'cambiar un campo extra conserva el resto de data', api.calls[1][2])

  await (await tb.prepare('update_item', { id: 't1', fields: { reminder: '2026-10-08T08:30' } })).run()
  ok(api.calls[2][2].data.reminder === '2026-10-08T08:30', 'recordatorio personalizado en data.reminder')
  await (await tb.prepare('update_item', { id: 't1', fields: { reminder: 'default' } })).run()
  ok(!('reminder' in api.calls[3][2].data), 'reminder "default" quita el personalizado')

  const pin = await tb.prepare('update_item', { id: 'n1', pinned: true })
  await pin.run()
  ok(api.calls[4][2].pinned === true && pin.title === 'Editar Nota: «Ideas viaje»', 'fijar un elemento', pin.title)

  const del = await tb.prepare('delete_item', { id: 'a1' })
  ok(del.kind === 'delete' && del.danger && del.title === 'Eliminar Aviso: «Gimnasio»', 'borrar se marca como peligroso con el nombre del elemento', del.title)
  await del.run()
  ok(!api.items_.some((i) => i.id === 'a1'), 'el elemento se borra al ejecutar')
  await throwsTool(() => tb.prepare('delete_item', { id: 'p1' }), /desactivado/, 'no se borra en módulos desactivados')
}

// ---------- Herramientas: consultas ----------
{
  const api = fakeApi(SEED)
  const tb = toolbox(api)
  const run = async (name, input) => (await tb.prepare(name, input)).run()
  const s1 = await run('search_items', { text: 'lisboa' })
  ok(s1.total === 1 && s1.items[0].id === 'n1', 'buscar texto dentro de las notas', s1)
  const s2 = await run('search_items', { module: 'tareas', include_done: false })
  ok(s2.total === 1 && s2.items[0].id === 't1', 'excluir lo completado', s2)
  const s3 = await run('search_items', { due_from: '2026-10-08', due_to: '2026-10-31' })
  ok(s3.items.map((i) => i.id).join() === 't1,a1', 'filtrar por rango de fechas', s3)
  const s4 = await run('search_items', {})
  ok(!s4.items.some((i) => i.module === 'peliculas'), 'las búsquedas generales ignoran módulos desactivados')
  const s5 = await run('search_items', { text: 'weekly' })
  ok(s5.total === 1, 'busca también en los campos extra')
  const ag = await run('get_agenda', { from: '2026-10-07', to: '2026-10-09' })
  ok(ag.total === 3, 'agenda entre dos fechas', ag)
  await throwsTool(() => tb.prepare('get_agenda', { from: '2026-10-09', to: '2026-10-01' }), /posterior/, 'agenda con fechas al revés -> error')
  const gi = await run('get_item', { id: 'n1' })
  ok(gi.item.body === 'Ir a Lisboa en primavera' && gi.reminders.length === 1, 'leer un elemento con sus avisos')
  const lm = await run('list_modules', {})
  ok(lm.modules.map((m) => m.id).join() === 'tareas,avisos,notas', 'list_modules: solo módulos activos con elementos', lm.modules.map((m) => m.id))
  ok(lm.modules[0].fields.find((f) => f.key === 'priority').options.join() === 'alta,media,baja', 'list_modules incluye las opciones válidas')
  const lf = await run('list_files', { text: 'casa' })
  ok(lf.total === 1 && lf.files[0].name === 'contrato.pdf' && !('path' in lf.files[0]), 'archivos: solo metadatos, sin ruta de Storage')
  const big = await run('search_items', { limit: 500 })
  ok(big.items.length <= 50, 'el límite de resultados está acotado')
}

// ---------- Permisos ----------
{
  const p = getAiPermissions({ ai: { permissions: { read: 'auto', create: 'auto', delete: 'auto', update: 'loquesea' } } })
  ok(p.delete === 'ask', 'borrar nunca puede ser automático')
  ok(p.update === 'ask', 'valores desconocidos vuelven al valor seguro')
  ok(JSON.stringify(getAiPermissions({})) === '{"read":"auto","create":"ask","update":"ask","delete":"ask"}', 'permisos por defecto: leer solo, el resto pregunta')
  ok(policyFor({ delete: 'auto' }, 'delete') === 'ask' && policyFor({}, undefined) === 'off', 'policyFor nunca permite borrar sin preguntar')
}

// ---------- Bucle del agente (modelo simulado) ----------
const toolUse = (id, name, input) => ({ type: 'tool_use', id, name, input })
const text = (t) => ({ type: 'text', text: t })

function scriptedModel(steps) {
  const seen = []
  let i = 0
  const send = async (msgs) => {
    seen.push(JSON.parse(JSON.stringify(msgs)))
    const step = typeof steps[i] === 'function' ? steps[i](msgs) : steps[i]
    i++
    if (!step) throw new Error('el modelo simulado no esperaba más llamadas')
    return step
  }
  return { send, seen, calls: () => i }
}

const user = (t) => ({ role: 'user', content: [text(t)] })

{
  const api = fakeApi(SEED)
  const model = scriptedModel([
    { stop_reason: 'tool_use', content: [{ type: 'thinking', thinking: '', signature: 'sig1' }, text('Miro tus tareas.'), toolUse('u1', 'search_items', { module: 'tareas' }), toolUse('u2', 'create_item', { module: 'tareas', fields: { title: 'Llamar a Ana', due_date: '2026-10-08' } })] },
    { stop_reason: 'end_turn', content: [text('Hecho: he creado la tarea.')] },
  ])
  const asked = []
  const actions = {}
  let snapshots = []
  const res = await runAgent({
    messages: [user('crea una tarea')],
    send: model.send,
    toolbox: toolbox(api),
    permissions: getAiPermissions({}),
    approve: async (list) => {
      asked.push(...list.map((a) => a.name))
      return new Set(list.map((a) => a.id))
    },
    onMessages: (m) => snapshots.push(m),
    onAction: (id, info) => (actions[id] = info),
  })
  ok(res.status === 'done' && model.calls() === 2, 'el agente termina tras responder con texto', res.status)
  ok(asked.join() === 'create_item', 'solo se pide confirmación para crear (leer es automático)', asked)
  const results = res.messages[2].content
  ok(results.length === 2 && results[0].tool_use_id === 'u1' && results[1].tool_use_id === 'u2', 'todos los resultados van en un único mensaje y en orden')
  ok(api.items_.some((i) => i.title === 'Llamar a Ana'), 'la tarea aprobada se crea')
  ok(actions.u2.status === 'done' && actions.u1.status === 'done', 'estado de cada acción registrado')
  ok(model.seen[1][1].content[0].signature === 'sig1', 'el razonamiento del modelo se devuelve intacto')
  const prefixOk = snapshots.every((s, k) => k === 0 || JSON.stringify(s.slice(0, snapshots[k - 1].length)) === JSON.stringify(snapshots[k - 1]))
  ok(prefixOk, 'el historial solo crece (nunca se edita)')
}

{
  const api = fakeApi(SEED)
  const model = scriptedModel([
    { stop_reason: 'tool_use', content: [toolUse('u1', 'delete_item', { id: 't1' })] },
    { stop_reason: 'end_turn', content: [text('Vale, no lo borro.')] },
  ])
  const res = await runAgent({ messages: [user('borra')], send: model.send, toolbox: toolbox(api), permissions: getAiPermissions({}), approve: async () => new Set() })
  ok(api.items_.some((i) => i.id === 't1') && api.calls.length === 0, 'acción rechazada: no se borra nada')
  ok(/rechazado/.test(res.messages[2].content[0].content) && !res.messages[2].content[0].is_error, 'el modelo recibe que el usuario lo rechazó')
}

{
  const api = fakeApi(SEED)
  const model = scriptedModel([
    { stop_reason: 'tool_use', content: [toolUse('u1', 'create_item', { module: 'tareas', fields: { title: 'X' } })] },
    { stop_reason: 'end_turn', content: [text('No tengo permiso.')] },
  ])
  let asked = false
  const res = await runAgent({
    messages: [user('crea')],
    send: model.send,
    toolbox: toolbox(api),
    permissions: getAiPermissions({ ai: { permissions: { create: 'off' } } }),
    approve: async () => {
      asked = true
      return new Set()
    },
  })
  ok(!asked && api.calls.length === 0 && res.messages[2].content[0].is_error, 'permiso desactivado: bloqueado sin preguntar')
}

{
  const api = fakeApi(SEED)
  const model = scriptedModel([
    { stop_reason: 'tool_use', content: [toolUse('u1', 'create_item', { module: 'tareas', fields: { title: 'X', priority: 'urgentísima' } })] },
    { stop_reason: 'tool_use', content: [toolUse('u2', 'create_item', { module: 'tareas', fields: { title: 'X', priority: 'alta' } })] },
    { stop_reason: 'end_turn', content: [text('Creada.')] },
  ])
  let asks = 0
  const res = await runAgent({
    messages: [user('crea')],
    send: model.send,
    toolbox: toolbox(api),
    permissions: getAiPermissions({}),
    approve: async (l) => {
      asks++
      return new Set(l.map((a) => a.id))
    },
  })
  ok(res.messages[2].content[0].is_error && asks === 1 && api.calls.length === 1, 'petición no válida: el modelo recibe el error y la corrige; solo se pregunta por la válida')
}

{
  const api = fakeApi(SEED)
  const many = Array.from({ length: MAX_WRITES_PER_TURN + 2 }, (_, k) => toolUse(`c${k}`, 'create_item', { module: 'notas', fields: { title: `Nota ${k}` } }))
  const model = scriptedModel([{ stop_reason: 'tool_use', content: many }, { stop_reason: 'end_turn', content: [text('ok')] }])
  const res = await runAgent({ messages: [user('muchas')], send: model.send, toolbox: toolbox(api), permissions: { ...getAiPermissions({}), create: 'auto' }, approve: async () => new Set() })
  const blocked = res.messages[2].content.filter((r) => r.is_error).length
  ok(api.calls.length === MAX_WRITES_PER_TURN && blocked === 2, `máximo ${MAX_WRITES_PER_TURN} cambios por mensaje`, { done: api.calls.length, blocked })
}

{
  const api = fakeApi(SEED)
  const model = scriptedModel([{ stop_reason: 'tool_use', content: [toolUse('u1', 'create_item', { module: 'notas', fields: { title: 'A' } })] }])
  let stopped = false
  const res = await runAgent({
    messages: [user('crea')],
    send: model.send,
    toolbox: toolbox(api),
    permissions: getAiPermissions({}),
    approve: async () => {
      stopped = true // el usuario pulsa «Detener» con la confirmación abierta
      return new Set()
    },
    isStopped: () => stopped,
  })
  ok(res.status === 'stopped' && model.calls() === 1 && api.calls.length === 0, 'detener: no se ejecuta nada ni se vuelve a llamar al modelo', res.status)
  ok(res.messages.at(-1).content[0].tool_use_id === 'u1', 'detener: la conversación queda bien formada (cada herramienta con su resultado)')
}

{
  const model = scriptedModel([{ stop_reason: 'refusal', content: [] }])
  const res = await runAgent({ messages: [user('x')], send: model.send, toolbox: toolbox(fakeApi()), permissions: getAiPermissions({}), approve: async () => new Set() })
  ok(res.status === 'refusal' && res.messages.at(-1).role === 'assistant' && res.messages.at(-1).content[0].type === 'text', 'rechazo del modelo: la conversación puede continuar')
}

{
  const loop = () => ({ stop_reason: 'tool_use', content: [toolUse(`r${Math.random()}`, 'list_modules', {})] })
  const model = scriptedModel(Array.from({ length: 50 }, () => loop))
  const res = await runAgent({ messages: [user('x')], send: model.send, toolbox: toolbox(fakeApi()), permissions: getAiPermissions({}), approve: async () => new Set() })
  ok(res.status === 'limit' && model.calls() === MAX_STEPS, `como máximo ${MAX_STEPS} llamadas al modelo por mensaje`, model.calls())
}

{
  // Reanudar una conversación guardada con una acción pendiente de confirmar
  const api = fakeApi(SEED)
  const msgs = [user('borra el pan'), { role: 'assistant', content: [toolUse('u9', 'delete_item', { id: 't2' })] }]
  const model = scriptedModel([{ stop_reason: 'end_turn', content: [text('Borrado.')] }])
  const res = await runAgent({ messages: msgs, send: model.send, toolbox: toolbox(api), permissions: getAiPermissions({}), approve: async (l) => new Set(l.map((a) => a.id)) })
  ok(res.status === 'done' && !api.items_.some((i) => i.id === 't2') && model.calls() === 1, 'reanudar: pide confirmación, ejecuta y continúa')
}

{
  const m = buildUserMessage('hola', { now: new Date('2026-10-07T22:30:00Z'), timezone: 'Europe/Madrid', userName: 'Paco' })
  ok(/hoy es 2026-10-08/.test(m.content[0].text) && m.content[1].text === 'hola', 'contexto de fecha en la zona del usuario (00:30 en Madrid = día siguiente)', m.content[0].text)
}

console.log(`\n${count - fail}/${count} pruebas correctas`)
if (fail) process.exit(1)
