// Reglas que convierten un elemento con fecha en avisos programados.
//
// Un módulo puede declarar `notifications` en su definición:
//   notifications: {
//     kind: 'task' | 'exam' | 'event' | 'custom' | 'system',
//     time: (prefs, item) => 'HH:MM',        // hora local del aviso
//     daysBefore: (prefs, item) => número,   // días antes de due_date
//     active: (item) => boolean,             // p. ej. no avisar de tareas hechas
//     message: (item, ctx) => ({ title, body }),
//   }
// Los módulos sin esa clave pero que aparecen en el calendario (showInCalendar) y tienen
// fecha reciben automáticamente un aviso de tipo "event" (incluidos los personalizados).
// Cada elemento puede sobrescribirlo en item.data.reminder:
//   undefined | 'default' -> regla del módulo
//   'none'                -> sin aviso
//   'YYYY-MM-DDTHH:MM'    -> fecha y hora concretas (hora local)
import { shiftDate, zonedToUtc } from './time'

const KIND_LABEL = { task: 'Tarea', exam: 'Examen', event: 'Evento', custom: 'Aviso', system: 'PACO OS' }

function whenText(days) {
  if (days === 0) return 'hoy'
  if (days === 1) return 'mañana'
  return `en ${days} días`
}

export function resolveNotificationConfig(module) {
  if (!module || module.usesItems === false) return null
  if (module.notifications) return module.notifications
  const hasDate = module.fields?.some((f) => f.key === 'due_date')
  if (!module.showInCalendar || !hasDate) return null
  return {
    kind: 'event',
    time: (prefs) => prefs.eventTime,
    daysBefore: () => 0,
    message: (item, { days }) => ({
      title: module.calendarLabel?.(item) || item.title || module.name,
      body: `${module.name} · ${whenText(days)}`,
    }),
  }
}

export function itemUrl(item) {
  return `#/m/${item.module}?item=${item.id}`
}

// Devuelve la lista de avisos que DEBERÍA tener un elemento: [{ dedupe_key, kind, title, body, url, remind_at }]
export function computeItemNotifications(item, module, prefs, now = new Date()) {
  const config = resolveNotificationConfig(module)
  if (!config || !item?.id) return []
  if (config.active && !config.active(item)) return []

  const override = item.data?.reminder
  if (override === 'none') return []

  let remindAt
  let days = 0
  if (override && override !== 'default') {
    const [date, time] = String(override).split('T')
    if (!date || !time) return []
    remindAt = zonedToUtc(date, time.slice(0, 5), prefs.timezone)
    // Días que faltan desde el aviso hasta la fecha del elemento (para el texto del mensaje)
    if (item.due_date) days = Math.max(0, Math.round((Date.parse(item.due_date) - Date.parse(date)) / 86400000))
  } else {
    if (!item.due_date) return []
    days = Math.max(0, Number(config.daysBefore?.(prefs, item)) || 0)
    const time = config.time?.(prefs, item) || '09:00'
    remindAt = zonedToUtc(shiftDate(item.due_date, -days), time, prefs.timezone)
  }

  if (Number.isNaN(remindAt.getTime()) || remindAt <= now) return []

  const msg = config.message?.(item, { days, module }) || {
    title: `${KIND_LABEL[config.kind] || 'Aviso'}: ${item.title || 'Sin título'}`,
    body: module.name,
  }
  return [
    {
      dedupe_key: `item:${item.id}`,
      kind: config.kind,
      title: msg.title,
      body: msg.body || '',
      url: itemUrl(item),
      remind_at: remindAt.toISOString(),
    },
  ]
}

// Texto descriptivo del aviso por defecto de un módulo, para el formulario.
export function describeDefaultReminder(module, prefs, item = {}) {
  const config = resolveNotificationConfig(module)
  if (!config) return ''
  const days = Math.max(0, Number(config.daysBefore?.(prefs, item)) || 0)
  const time = config.time?.(prefs, item) || '09:00'
  const day = days === 0 ? 'el mismo día' : days === 1 ? 'el día anterior' : `${days} días antes`
  return `${day} a las ${time}`
}
