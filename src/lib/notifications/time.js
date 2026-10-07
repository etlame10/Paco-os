// Conversión entre "hora local en una zona horaria" e instantes UTC, sin librerías.
// Tiene en cuenta los cambios de horario de verano/invierno.

function partsInZone(ts, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(ts))
  const get = (t) => Number(parts.find((p) => p.type === t).value)
  return { y: get('year'), m: get('month'), d: get('day'), h: get('hour'), min: get('minute'), s: get('second') }
}

function offsetMs(ts, timeZone) {
  const p = partsInZone(ts, timeZone)
  return Date.UTC(p.y, p.m - 1, p.d, p.h, p.min, p.s) - Math.floor(ts / 1000) * 1000
}

// "2026-10-20", "09:00", "Europe/Madrid" -> Date (instante UTC correspondiente)
export function zonedToUtc(dateStr, timeStr, timeZone) {
  const [y, m, d] = dateStr.split('-').map(Number)
  const [hh, mm] = (timeStr || '09:00').split(':').map(Number)
  const guess = Date.UTC(y, m - 1, d, hh, mm)
  const off1 = offsetMs(guess, timeZone)
  let t = guess - off1
  const off2 = offsetMs(t, timeZone)
  if (off2 !== off1) t = guess - off2
  return new Date(t)
}

// Fecha y hora local (en la zona indicada) de un instante: { date: 'YYYY-MM-DD', time: 'HH:MM' }
export function utcToZoned(date, timeZone) {
  const p = partsInZone(new Date(date).getTime(), timeZone)
  const pad = (n) => String(n).padStart(2, '0')
  return { date: `${p.y}-${pad(p.m)}-${pad(p.d)}`, time: `${pad(p.h)}:${pad(p.min)}` }
}

export function shiftDate(dateStr, days) {
  const [y, m, d] = dateStr.split('-').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d + days))
  return t.toISOString().slice(0, 10)
}

const toMinutes = (hhmm) => {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

// ¿Está el instante dentro de las horas de silencio? (admite franjas que cruzan medianoche)
export function inQuietHours(date, prefs) {
  if (!prefs.quietStart || !prefs.quietEnd || prefs.quietStart === prefs.quietEnd) return false
  const now = toMinutes(utcToZoned(date, prefs.timezone).time)
  const start = toMinutes(prefs.quietStart)
  const end = toMinutes(prefs.quietEnd)
  return start < end ? now >= start && now < end : now >= start || now < end
}

export function formatDateTime(date, timeZone) {
  return new Intl.DateTimeFormat('es-ES', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date))
}

export function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    return 'Europe/Madrid'
  }
}
