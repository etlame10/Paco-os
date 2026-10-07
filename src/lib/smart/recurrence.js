// Repeticiones de elementos (tareas, avisos y cualquier módulo que declare `recurrence`).
// Sin dependencias.
import { REPEAT_LABELS } from './parseQuick.js'

export { REPEAT_LABELS }

export const REPEAT_OPTIONS = Object.entries(REPEAT_LABELS).map(([value, label]) => ({ value, label }))

const pad = (n) => String(n).padStart(2, '0')
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const parse = (s) => {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

// Suma meses manteniendo el día; si no existe (31 de febrero) usa el último día del mes.
function addMonths(date, n, anchorDay) {
  const target = new Date(date.getFullYear(), date.getMonth() + n, 1)
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
  return new Date(target.getFullYear(), target.getMonth(), Math.min(anchorDay, last))
}

function step(date, repeat, anchorDay) {
  switch (repeat) {
    case 'daily':
      return new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1)
    case 'weekdays': {
      let d = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1)
      while (d.getDay() === 0 || d.getDay() === 6) d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)
      return d
    }
    case 'weekly':
      return new Date(date.getFullYear(), date.getMonth(), date.getDate() + 7)
    case 'biweekly':
      return new Date(date.getFullYear(), date.getMonth(), date.getDate() + 14)
    case 'monthly':
      return addMonths(date, 1, anchorDay)
    case 'yearly':
      return addMonths(date, 12, anchorDay)
    default:
      return null
  }
}

// Siguiente fecha (YYYY-MM-DD) estrictamente posterior a `today` y a `fromDate`.
// Si el elemento estaba atrasado, salta las repeticiones ya pasadas.
export function nextOccurrence(fromDate, repeat, today) {
  if (!REPEAT_LABELS[repeat]) return null
  const anchorDay = parse(fromDate).getDate()
  const limit = parse(today)
  let d = step(parse(fromDate), repeat, anchorDay)
  for (let i = 0; d && d <= limit && i < 5000; i++) d = step(d, repeat, anchorDay)
  return d ? iso(d) : null
}

export function daysBetween(a, b) {
  return Math.round((parse(b) - parse(a)) / 86400000)
}

export function shiftDate(dateStr, days) {
  const d = parse(dateStr)
  return iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + days))
}
