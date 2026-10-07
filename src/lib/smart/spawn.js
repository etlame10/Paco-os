// Crea la siguiente repetición cuando se completa un elemento repetitivo.
//
// Un módulo lo activa declarando en su definición:
//   recurrence: { doneStatus: 'hecha', openStatus: 'pendiente' }
// y un campo `repeat` (daily | weekdays | weekly | biweekly | monthly | yearly) en item.data.
//
// El elemento completado se conserva como historial y guarda en data.nextId el id del
// siguiente, así que desmarcarlo y volverlo a marcar no crea duplicados.
import { getRuntimeContext, emitItemsChanged } from '../runtimeContext'
import { nextOccurrence, daysBetween, shiftDate } from './recurrence'

const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export async function spawnNextIfRecurring(backend, items, row) {
  const module = getRuntimeContext().getModule(row?.module)
  const rec = module?.recurrence
  const repeat = row?.data?.repeat
  if (!rec || !repeat || row.status !== rec.doneStatus || row.data?.nextId) return null

  const base = row.due_date || todayISO()
  const nextDate = nextOccurrence(base, repeat, todayISO())
  if (!nextDate) return null

  const data = { ...row.data }
  delete data.nextId
  // Un recordatorio con fecha y hora concretas se desplaza lo mismo que la fecha.
  const reminder = data.reminder
  if (reminder && reminder !== 'default' && reminder !== 'none' && reminder.includes('T')) {
    const [d, t] = reminder.split('T')
    data.reminder = `${shiftDate(d, daysBetween(base, nextDate))}T${t}`
  }

  const next = await items.create({
    module: row.module,
    title: row.title,
    body: row.body,
    tags: row.tags || [],
    status: rec.openStatus,
    due_date: nextDate,
    pinned: row.pinned,
    data,
  })
  await backend.items.update(row.id, { data: { ...row.data, nextId: next.id } })
  emitItemsChanged({ module: row.module, type: 'recurrence', item: next })
  return next
}
