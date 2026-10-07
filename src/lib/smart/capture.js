// Convierte lo que entiende parseQuick() en un elemento listo para guardar en un módulo.
import { defaultForm, formToItem } from '../items'

const hasField = (module, key) => module?.fields?.some((f) => f.key === key)

// Destino automático: con hora -> Avisos; con o sin fecha -> Tareas; si no, el primer módulo.
export function autoModule(parsed, modules) {
  const byId = (id) => modules.find((m) => m.id === id)
  if (parsed.time && byId('avisos')) return byId('avisos')
  return byId('tareas') || byId('avisos') || modules.find((m) => m.usesItems !== false) || null
}

// ¿Tiene sentido aplicar fecha/hora/repetición en este módulo?
export function moduleAcceptsSchedule(module) {
  return hasField(module, 'due_date')
}

export function buildCaptureItem(parsed, module, rawText) {
  const smart = moduleAcceptsSchedule(module) && parsed.understood
  const values = { title: smart ? parsed.title : rawText.trim() }
  if (smart) {
    if (parsed.date) values.due_date = parsed.date
    if (parsed.repeat && hasField(module, 'repeat')) values.repeat = parsed.repeat
    if (parsed.priority && hasField(module, 'priority')) values.priority = parsed.priority
    if (parsed.time && hasField(module, 'hora')) values.hora = parsed.time
  }
  const item = formToItem(defaultForm(module.fields || [], values))
  // En módulos sin campo "hora" (p. ej. Tareas), la hora se convierte en un recordatorio concreto.
  if (smart && parsed.time && parsed.date && !hasField(module, 'hora')) {
    item.data = { ...item.data, reminder: `${parsed.date}T${parsed.time}` }
  }
  return item
}
