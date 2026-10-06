export const cx = (...c) => c.filter(Boolean).join(' ')

export const todayISO = () => toISODate(new Date())

export function toISODate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function parseISODate(s) {
  if (!s) return null
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(date, n) {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

export function daysUntil(iso) {
  const d = parseISODate(iso)
  if (!d) return null
  const t = parseISODate(todayISO())
  return Math.round((d - t) / 86400000)
}

const dateFmt = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' })
const dateFmtYear = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })

export function formatDate(iso) {
  const d = parseISODate(iso)
  if (!d) return ''
  return d.getFullYear() === new Date().getFullYear() ? dateFmt.format(d) : dateFmtYear.format(d)
}

export function relativeDay(iso) {
  const n = daysUntil(iso)
  if (n === null) return ''
  if (n === 0) return 'Hoy'
  if (n === 1) return 'Mañana'
  if (n === -1) return 'Ayer'
  if (n > 1 && n < 7) return `En ${n} días`
  if (n < -1 && n > -7) return `Hace ${-n} días`
  return formatDate(iso)
}

export function timeAgo(ts) {
  const s = Math.round((Date.now() - new Date(ts).getTime()) / 1000)
  if (s < 60) return 'ahora'
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`
  if (s < 86400 * 30) return `hace ${Math.floor(s / 86400)} d`
  return new Date(ts).toLocaleDateString('es-ES')
}

export function formatBytes(b) {
  if (!b) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), u.length - 1)
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`
}

const money = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
export const formatMoney = (n) => money.format(Number(n) || 0)

export function slugify(s) {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

export function downloadText(filename, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function greeting() {
  const h = new Date().getHours()
  if (h < 6) return 'Buenas noches'
  if (h < 14) return 'Buenos días'
  if (h < 21) return 'Buenas tardes'
  return 'Buenas noches'
}
