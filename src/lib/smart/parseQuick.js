// Intérprete de lenguaje natural (español) para la captura rápida.
// Sin dependencias: recibe un texto y devuelve qué ha entendido.
//
//   parseQuick('llamar al dentista mañana a las 17:30')
//   -> { title: 'Llamar al dentista', date: '2026-10-08', time: '17:30', repeat: null, priority: null }
//
// Entiende:
//   fechas    hoy, mañana, pasado mañana, el lunes / el próximo viernes, en 3 días, dentro de 2 semanas,
//             el 15, el 15 de octubre, 15/10, 15/10/2027, esta tarde / esta noche
//   horas     a las 17, a las 17:30, 17:30, 17h, a las 5 de la tarde, a las 9 y media, por la mañana,
//             al mediodía, por la tarde, por la noche
//   repetir   todos los días, entre semana, cada semana, cada lunes, cada 2 semanas, cada mes, cada año
//   prioridad !alta, !media, !baja

const WEEKDAYS = ['domingo', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado']
const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const NUMBERS = { un: 1, una: 1, uno: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10, quince: 15 }

export const REPEAT_LABELS = {
  daily: 'Cada día',
  weekdays: 'Entre semana',
  weekly: 'Cada semana',
  biweekly: 'Cada 2 semanas',
  monthly: 'Cada mes',
  yearly: 'Cada año',
}

const WD = '(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)'
const NUM = '(\\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince)'

// Quita tildes (y ñ -> n) sin cambiar la longitud del texto (para poder recortar el original por posiciones).
function fold(s) {
  const map = { á: 'a', é: 'e', í: 'i', ó: 'o', ú: 'u', ü: 'u', ñ: 'n', Á: 'a', É: 'e', Í: 'i', Ó: 'o', Ú: 'u', Ü: 'u', Ñ: 'n' }
  return s.replace(/[áéíóúüñÁÉÍÓÚÜÑ]/g, (c) => map[c]).toLowerCase()
}

const pad = (n) => String(n).padStart(2, '0')
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const plusDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
const toNum = (s) => (/^\d+$/.test(s) ? Number(s) : NUMBERS[s] ?? NaN)
const weekdayIndex = (w) => WEEKDAYS.indexOf(w.replace(/^(sabado|domingo)s$/, '$1'))

function nextWeekday(today, idx, forceNext) {
  let diff = (idx - today.getDay() + 7) % 7
  if (forceNext && diff === 0) diff = 7
  return plusDays(today, diff)
}

export function parseQuick(input, now = new Date()) {
  const original = String(input || '')
  let text = fold(original)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const removed = [] // tramos [inicio, fin) a quitar del título
  const out = { date: null, time: null, repeat: null, priority: null }
  let dayPart = null // 'morning' | 'afternoon' | 'night'

  // Ejecuta una expresión y, si coincide, marca el tramo para borrarlo del título.
  const take = (re, fn) => {
    const m = re.exec(text)
    if (!m) return false
    if (fn(m) === false) return false
    removed.push([m.index, m.index + m[0].length])
    text = text.slice(0, m.index) + ' '.repeat(m[0].length) + text.slice(m.index + m[0].length)
    return true
  }

  // ---- Prioridad ----
  take(/(^|\s)!(alta|media|baja)\b/, (m) => (out.priority = m[2]))

  // ---- Repetición ----
  take(/\b(todos los dias|cada dia|a diario|diariamente)\b/, () => (out.repeat = 'daily'))
  take(/\b(entre semana|de lunes a viernes|(?:los |todos los )?dias laborables)\b/, () => (out.repeat = 'weekdays'))
  take(/\bcada (?:2|dos) semanas\b/, () => (out.repeat = 'biweekly'))
  take(new RegExp(`\\b(?:cada|todos los|todas las) ${WD}\\b`), (m) => {
    out.repeat = 'weekly'
    out.date = iso(nextWeekday(today, weekdayIndex(m[1]), false))
  })
  take(/\b(cada semana|todas las semanas|semanalmente)\b/, () => (out.repeat = 'weekly'))
  take(/\b(cada mes|todos los meses|mensualmente)\b/, () => (out.repeat = 'monthly'))
  take(/\b(cada ano|todos los anos|anualmente)\b/, () => (out.repeat = 'yearly'))

  // ---- Franjas del día (antes que "mañana" = día siguiente) ----
  take(/\b(?:por|de) la manana\b/, () => (dayPart = 'morning'))
  take(/\b(?:al|a) mediodia\b/, () => (out.time = '13:00'))
  take(/\besta tarde\b/, () => {
    dayPart = 'afternoon'
    out.date ??= iso(today)
  })
  take(/\besta noche\b/, () => {
    dayPart = 'night'
    out.date ??= iso(today)
  })
  take(/\b(?:por|de) la tarde\b/, () => (dayPart = 'afternoon'))
  take(/\b(?:por|de) la noche\b/, () => (dayPart = 'night'))

  // ---- Fechas ----
  if (!out.date) {
    take(/\bpasado manana\b/, () => (out.date = iso(plusDays(today, 2)))) ||
      take(/\bmanana\b/, () => (out.date = iso(plusDays(today, 1)))) ||
      take(/\bhoy\b/, () => (out.date = iso(today))) ||
      take(new RegExp(`\\b(?:en|dentro de) ${NUM} (dias?|semanas?|mes|meses)\\b`), (m) => {
        const n = toNum(m[1])
        if (!n) return false
        if (m[2].startsWith('dia')) out.date = iso(plusDays(today, n))
        else if (m[2].startsWith('semana')) out.date = iso(plusDays(today, n * 7))
        else out.date = iso(new Date(today.getFullYear(), today.getMonth() + n, today.getDate()))
      }) ||
      take(/\b(?:el )?(\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?: de(?:l)? (\d{4}))?\b/, (m) => {
        const day = Number(m[1])
        const month = m[2] === 'setiembre' ? 8 : MONTHS.indexOf(m[2])
        let year = m[3] ? Number(m[3]) : today.getFullYear()
        let d = new Date(year, month, day)
        if (d.getMonth() !== month) return false
        if (!m[3] && d < today) d = new Date(++year, month, day)
        out.date = iso(d)
      }) ||
      take(/\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2}|\d{4}))?\b/, (m) => {
        const day = Number(m[1])
        const month = Number(m[2]) - 1
        if (month < 0 || month > 11) return false
        let year = m[3] ? Number(m[3].length === 2 ? '20' + m[3] : m[3]) : today.getFullYear()
        let d = new Date(year, month, day)
        if (d.getMonth() !== month) return false
        if (!m[3] && d < today) d = new Date(++year, month, day)
        out.date = iso(d)
      }) ||
      take(new RegExp(`\\b(?:el |este |esta )?(?:proximo |que viene )?${WD}(?: que viene| proximo)?\\b`), (m) => {
        // "Martes y 13", "Viernes 13"...: en mayúscula y en mitad del texto se trata como parte del título.
        const at = m.index + m[0].indexOf(m[1])
        if (at > 0 && /[A-ZÁÉÍÓÚÑ]/.test(original[at])) return false
        const forceNext = /proximo|que viene/.test(m[0])
        out.date = iso(nextWeekday(today, weekdayIndex(m[1]), forceNext))
      }) ||
      take(/\bel (?:dia )?(\d{1,2})\b(?!\s*(?::|h\b|horas?\b))/, (m) => {
        const day = Number(m[1])
        if (day < 1 || day > 31) return false
        let d = new Date(today.getFullYear(), today.getMonth(), day)
        if (d.getDate() !== day) return false
        if (d < today) d = new Date(today.getFullYear(), today.getMonth() + 1, day)
        out.date = iso(d)
      })
  }

  // ---- Horas ----
  if (!out.time) {
    const fix = (h, min, part) => {
      if (h > 23 || min > 59) return false
      if ((part === 'afternoon' || part === 'night') && h < 12) h += 12
      if (part === 'morning' && h === 12) h = 0
      out.time = `${pad(h)}:${pad(min)}`
    }
    const suffix = '(?:\\s*(?:h|hs|horas))?(?: (y media|y cuarto|menos cuarto))?(?: de la (manana|tarde|noche)|\\s*(am|pm))?'
    const partOf = (m5, m6) =>
      m5 === 'manana' || m6 === 'am' ? 'morning' : m5 === 'tarde' || m6 === 'pm' ? 'afternoon' : m5 === 'noche' ? 'night' : dayPart
    const minutesOf = (mm, frac) => (mm != null ? Number(mm) : frac === 'y media' ? 30 : frac === 'y cuarto' ? 15 : 0)
    take(new RegExp(`\\ba (?:las|la) (\\d{1,2})(?:[:.](\\d{2}))?${suffix}\\b`), (m) => {
      let h = Number(m[1])
      let min = minutesOf(m[2], m[3])
      if (m[3] === 'menos cuarto') {
        h -= 1
        min = 45
      }
      return fix(h, min, partOf(m[4], m[5]))
    }) ||
      take(new RegExp(`\\b(\\d{1,2})[:.](\\d{2})${suffix}\\b`), (m) => fix(Number(m[1]), Number(m[2]), partOf(m[4], m[5]))) ||
      take(/\b(\d{1,2})\s*(?:h|hs)\b/, (m) => fix(Number(m[1]), 0, dayPart))
  }
  if (!out.time && dayPart) out.time = { morning: '09:00', afternoon: '17:00', night: '21:00' }[dayPart]

  // Hora sin fecha: hoy si aún no ha pasado; si no, mañana.
  if (out.time && !out.date) {
    const [h, m] = out.time.split(':').map(Number)
    const passed = now.getHours() * 60 + now.getMinutes() >= h * 60 + m
    out.date = iso(passed && !out.repeat ? plusDays(today, 1) : today)
  }
  // Repetición sin fecha: empieza hoy.
  if (out.repeat && !out.date) out.date = iso(today)

  // ---- Título: el texto original sin las partes reconocidas ----
  let title = ''
  let last = 0
  for (const [a, b] of removed.sort((x, y) => x[0] - y[0])) {
    title += original.slice(last, a) + ' '
    last = b
  }
  title += original.slice(last)
  title = title.replace(/\s+/g, ' ').trim()
  // Conectores sueltos que quedan al final o al principio ("llamar a mamá el" -> "llamar a mamá")
  for (let i = 0; i < 3; i++) {
    title = title
      .replace(/[\s,;:-]+(el|la|los|las|a|al|de|del|para|en|y|e|que|desde|este|esta|recordar|recuerdame)$/i, '')
      .replace(/^(recordar|recuérdame|recuerdame|recordarme|tengo que|hay que)\s+/i, '')
      .replace(/[\s,;:-]+$/, '')
      .trim()
  }
  if (!title) title = original.trim()
  title = title.charAt(0).toUpperCase() + title.slice(1)

  return { title, ...out, understood: Boolean(out.date || out.time || out.repeat || out.priority) }
}
