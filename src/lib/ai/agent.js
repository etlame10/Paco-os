// Bucle del agente PACO AI (se ejecuta en el navegador).
//
//   1. Se envía la conversación a la Edge Function "paco-ai", que llama al modelo.
//   2. Si el modelo pide herramientas, se validan aquí (tools.js) y se aplican los
//      permisos (permissions.js): lo de solo lectura se ejecuta, lo sensible espera
//      a que el usuario lo apruebe en pantalla.
//   3. Los resultados vuelven al modelo y se repite hasta que responde con texto.
//
// El historial solo crece (nunca se edita ni se recorta) y se reenvía íntegro,
// incluidas las firmas de razonamiento del modelo (`signature`), que el proveedor
// necesita para continuar correctamente tras usar herramientas.
import { policyFor } from './permissions.js'

export const MAX_STEPS = 10 // llamadas al modelo por cada mensaje del usuario
export const MAX_WRITES_PER_TURN = 15 // cambios (crear/editar/borrar) por cada mensaje del usuario
const MAX_RESULT_CHARS = 45000 // cabe un tramo de documento (~40.000 caracteres)
const WRITE_KINDS = new Set(['create', 'update', 'delete'])

export const CONTEXT_PREFIX = '<contexto_app>'

// Mensaje del usuario + contexto actual (fecha, hora, zona) que el modelo necesita
// para entender «mañana» o «el viernes». La interfaz no muestra el bloque de contexto.
// Documentos adjuntados por el usuario en este mensaje: quedan autorizados para leerse.
export const ATTACH_PREFIX = '<documentos_adjuntos>'

export function buildUserMessage(text, { now = new Date(), timezone, userName, attachments = [] } = {}) {
  const tz = timezone || Intl.DateTimeFormat().resolvedOptions().timeZone
  const fmt = new Intl.DateTimeFormat('es-ES', { timeZone: tz, weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now).map((p) => [p.type, p.value]))
  const iso = `${parts.year}-${parts.month}-${parts.day}`
  const ctx = `${CONTEXT_PREFIX}Ahora: ${fmt.format(now)} (hoy es ${iso}, zona ${tz}).${userName ? ` Usuario: ${userName}.` : ''}</contexto_app>`
  const content = [{ type: 'text', text: ctx }]
  if (attachments.length) {
    const list = attachments.map((f) => `- «${String(f.name).replace(/[<>«»]/g, '')}» (file_id: ${f.id})`).join('\n')
    content.push({ type: 'text', text: `${ATTACH_PREFIX}El usuario adjunta estos documentos y te autoriza a leerlos con read_document:\n${list}</documentos_adjuntos>` })
  }
  content.push({ type: 'text', text })
  return { role: 'user', content }
}

// Nombres de los documentos adjuntos de un mensaje (para mostrarlos en la interfaz).
export function attachmentNames(msg) {
  const block = Array.isArray(msg?.content) ? msg.content.find((b) => b.type === 'text' && b.text.startsWith(ATTACH_PREFIX)) : null
  return block ? [...block.text.matchAll(/«([^»]*)»/g)].map((m) => m[1]) : []
}

export const toolUsesOf = (msg) => (msg?.role === 'assistant' && Array.isArray(msg.content) ? msg.content.filter((b) => b.type === 'tool_use') : [])

// Herramientas que el último mensaje del modelo pidió y aún no tienen respuesta.
export function pendingToolUses(messages) {
  return toolUsesOf(messages[messages.length - 1])
}

function resultBlock(id, payload, isError = false) {
  let content = typeof payload === 'string' ? payload : JSON.stringify(payload)
  if (content.length > MAX_RESULT_CHARS) content = content.slice(0, MAX_RESULT_CHARS) + '… [resultado recortado: usa filtros más concretos]'
  return { type: 'tool_result', tool_use_id: id, content, ...(isError ? { is_error: true } : {}) }
}

/**
 * Ejecuta el agente hasta que el modelo termina, pide confirmación rechazada, etc.
 * opts:
 *   messages      historial actual (el último suele ser el mensaje nuevo del usuario)
 *   send(msgs)    llama a la Edge Function -> { content, stop_reason }
 *   toolbox       createToolbox(...)
 *   permissions   getAiPermissions(settings)
 *   approve(list) muestra las acciones y resuelve con un Set de ids aprobados
 *   onMessages(m) cada vez que el historial crece (para pintar y guardar)
 *   onAction(id, info) estado de cada acción: { title, kind, status, details, error }
 *   isStopped()   true si el usuario pulsó «Detener»
 *   approvedKeys  autorizaciones ya dadas en esta conversación (p. ej. leer un documento)
 *   onRemember(k) se llama cuando el usuario aprueba algo que debe recordarse
 * Seguridad: si la conversación incluye el contenido de un documento, cualquier cambio
 * (crear/editar/borrar) pide confirmación aunque el usuario lo tenga en «Sin preguntar»:
 * así un texto escondido en un PDF nunca puede modificar datos por sí solo.
 * Devuelve { status: 'done' | 'refusal' | 'max_tokens' | 'limit' | 'stopped' }
 */
export async function runAgent({
  messages,
  send,
  toolbox,
  permissions,
  approve,
  onMessages = () => {},
  onAction = () => {},
  isStopped = () => false,
  approvedKeys = new Set(), // documentos ya autorizados en esta conversación ("file:<id>")
  onRemember = () => {},
}) {
  const msgs = [...messages]
  const push = (m) => {
    msgs.push(m)
    onMessages([...msgs])
  }
  let steps = 0
  let writes = 0

  while (true) {
    const pending = pendingToolUses(msgs)
    if (pending.length) {
      const stopped = isStopped()
      const results = await handleTools(pending, stopped)
      push({ role: 'user', content: results })
      if (stopped) return { status: 'stopped', messages: msgs }
      continue
    }
    const last = msgs[msgs.length - 1]
    if (!last || last.role !== 'user') return { status: 'done', messages: msgs }
    if (isStopped()) return { status: 'stopped', messages: msgs }
    if (steps >= MAX_STEPS) return { status: 'limit', messages: msgs }
    steps++

    const res = await send(msgs)
    const content = Array.isArray(res.content) ? res.content : []

    if (res.stop_reason === 'refusal') {
      // Se deja constancia en el historial para que la conversación pueda continuar.
      push({ role: 'assistant', content: [{ type: 'text', text: 'No puedo ayudarte con esa petición.' }] })
      return { status: 'refusal', messages: msgs }
    }
    if (!content.some((b) => (b.type === 'text' && b.text.trim()) || b.type === 'tool_use')) {
      push({ role: 'assistant', content: [...content, { type: 'text', text: '…' }] })
      return { status: res.stop_reason === 'max_tokens' ? 'max_tokens' : 'done', messages: msgs }
    }
    push({ role: 'assistant', content })
    if (res.stop_reason === 'max_tokens') {
      // Una herramienta cortada a medias no se ejecuta.
      const cut = toolUsesOf(msgs[msgs.length - 1])
      if (cut.length) push({ role: 'user', content: cut.map((u) => resultBlock(u.id, 'La respuesta se cortó antes de terminar; no se ha ejecutado.', true)) })
      return { status: 'max_tokens', messages: msgs }
    }
    if (res.stop_reason !== 'tool_use') return { status: 'done', messages: msgs }
  }

  async function handleTools(uses, stopped) {
    const results = new Map()
    const ready = []
    const toAsk = []
    let plannedWrites = writes
    const documentInContext = msgs.some((m) => toolUsesOf(m).some((u) => u.name === 'read_document'))

    for (const u of uses) {
      if (stopped) {
        results.set(u.id, resultBlock(u.id, 'El usuario ha detenido la conversación; no se ha ejecutado.', true))
        continue
      }
      let prepared
      try {
        prepared = await toolbox.prepare(u.name, u.input)
      } catch (e) {
        results.set(u.id, resultBlock(u.id, `Error: ${e.message || 'petición no válida'}`, true))
        onAction(u.id, { title: u.name, kind: null, status: 'error', error: e.message })
        continue
      }
      const action = { id: u.id, ...prepared }
      const info = { title: action.title, kind: action.kind, module: action.module, details: action.details, danger: action.danger }
      let policy = policyFor(permissions, action.kind)
      if (policy === 'auto' && documentInContext && WRITE_KINDS.has(action.kind)) policy = 'ask'
      if (policy === 'ask' && action.approvalKey && approvedKeys.has(action.approvalKey)) policy = 'auto'
      if (policy === 'off') {
        results.set(u.id, resultBlock(u.id, `Acción no permitida: el usuario ha desactivado este tipo de acción (${action.kind}) para PACO AI. Puede cambiarlo en Ajustes → PACO AI.`, true))
        onAction(u.id, { ...info, status: 'blocked' })
        continue
      }
      if (WRITE_KINDS.has(action.kind)) {
        if (plannedWrites >= MAX_WRITES_PER_TURN) {
          results.set(u.id, resultBlock(u.id, `Límite de ${MAX_WRITES_PER_TURN} cambios por mensaje alcanzado. Pide al usuario que continúe en otro mensaje.`, true))
          onAction(u.id, { ...info, status: 'blocked' })
          continue
        }
        plannedWrites++
      }
      if (policy === 'ask') {
        toAsk.push(action)
        onAction(u.id, { ...info, status: 'pending' })
      } else ready.push(action)
    }

    if (toAsk.length) {
      const approved = await approve(toAsk)
      for (const a of toAsk) {
        if (approved?.has(a.id)) {
          ready.push(a)
          if (a.approvalKey && !approvedKeys.has(a.approvalKey)) {
            approvedKeys.add(a.approvalKey)
            onRemember(a.approvalKey)
          }
        } else {
          results.set(a.id, resultBlock(a.id, 'El usuario ha rechazado esta acción y no se ha realizado. No la repitas salvo que te lo pida.'))
          onAction(a.id, { title: a.title, kind: a.kind, module: a.module, details: a.details, danger: a.danger, status: 'rejected' })
        }
      }
    }

    // Se ejecutan en el orden en que las pidió el modelo.
    for (const u of uses) {
      const a = ready.find((r) => r.id === u.id)
      if (!a) continue
      const info = { title: a.title, kind: a.kind, module: a.module, details: a.details, danger: a.danger }
      try {
        const out = await a.run()
        if (WRITE_KINDS.has(a.kind)) writes++
        results.set(u.id, resultBlock(u.id, out))
        onAction(u.id, { ...info, status: 'done' })
      } catch (e) {
        results.set(u.id, resultBlock(u.id, `Error al ejecutar: ${e.message || 'desconocido'}`, true))
        onAction(u.id, { ...info, status: 'error', error: e.message })
      }
    }
    return uses.map((u) => results.get(u.id))
  }
}
