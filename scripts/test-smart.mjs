// Pruebas del intérprete de lenguaje natural y de las repeticiones.
// Uso: npm run test:smart   (fecha de referencia fija: miércoles 7-oct-2026, 10:00)
import { parseQuick } from '../src/lib/smart/parseQuick.js'
import { nextOccurrence } from '../src/lib/smart/recurrence.js'

const NOW = new Date(2026, 9, 7, 10, 0)
let fail = 0
const eq = (got, exp, msg) => {
  const ok = Object.entries(exp).every(([k, v]) => got[k] === v)
  console.log(`${ok ? '✔' : '✘'} ${msg}`)
  if (!ok) {
    fail++
    console.log('    esperado:', exp, '\n    obtenido:', got)
  }
}
const p = (t) => parseQuick(t, NOW)

// --- Fechas ---
eq(p('Llamar al dentista mañana a las 17:30'), { title: 'Llamar al dentista', date: '2026-10-08', time: '17:30' }, 'mañana + hora')
eq(p('examen de física el viernes'), { title: 'Examen de física', date: '2026-10-09', time: null }, 'el viernes (esta semana)')
eq(p('reunión el próximo miércoles'), { title: 'Reunión', date: '2026-10-14' }, 'el próximo miércoles (hoy es miércoles)')
eq(p('reunión el miércoles'), { date: '2026-10-07' }, 'el miércoles = hoy')
eq(p('pagar la luz pasado mañana'), { title: 'Pagar la luz', date: '2026-10-09' }, 'pasado mañana')
eq(p('revisar coche en 3 días'), { title: 'Revisar coche', date: '2026-10-10' }, 'en 3 días')
eq(p('renovar DNI dentro de dos semanas'), { title: 'Renovar DNI', date: '2026-10-21' }, 'dentro de dos semanas')
eq(p('cumpleaños de Ana el 15 de noviembre'), { title: 'Cumpleaños de Ana', date: '2026-11-15' }, 'el 15 de noviembre')
eq(p('cita el 2 de marzo'), { date: '2027-03-02' }, 'fecha ya pasada este año -> año siguiente')
eq(p('entregar trabajo 20/10'), { title: 'Entregar trabajo', date: '2026-10-20' }, 'formato 20/10')
eq(p('viaje 3/1/2027'), { date: '2027-01-03' }, 'formato 3/1/2027')
eq(p('pagar alquiler el 1'), { title: 'Pagar alquiler', date: '2026-11-01' }, 'el 1 (ya pasó este mes -> siguiente)')
eq(p('comprar pan hoy'), { title: 'Comprar pan', date: '2026-10-07' }, 'hoy')
eq(p('estudiar en 1 mes'), { date: '2026-11-07' }, 'en 1 mes')

// --- Horas ---
eq(p('cena con Marta a las 9 de la noche'), { title: 'Cena con Marta', time: '21:00', date: '2026-10-07' }, 'a las 9 de la noche (hoy)')
eq(p('gimnasio a las 5 de la tarde'), { title: 'Gimnasio', time: '17:00' }, 'a las 5 de la tarde')
eq(p('llamar a mamá a las 9'), { title: 'Llamar a mamá', time: '09:00', date: '2026-10-08' }, 'a las 9 ya pasado -> mañana')
eq(p('médico mañana a las 9 y media'), { title: 'Médico', date: '2026-10-08', time: '09:30' }, 'y media')
eq(p('clase a las 6 menos cuarto de la tarde'), { time: '17:45' }, 'menos cuarto')
eq(p('reunión 16:15'), { title: 'Reunión', time: '16:15', date: '2026-10-07' }, '16:15 sin "a las"')
eq(p('tomar pastilla 22h'), { title: 'Tomar pastilla', time: '22:00' }, '22h')
eq(p('correr mañana por la mañana'), { title: 'Correr', date: '2026-10-08', time: '09:00' }, 'mañana por la mañana')
eq(p('regar plantas esta tarde'), { title: 'Regar plantas', date: '2026-10-07', time: '17:00' }, 'esta tarde')
eq(p('sacar la basura esta noche'), { title: 'Sacar la basura', time: '21:00' }, 'esta noche')
eq(p('comida al mediodía'), { title: 'Comida', time: '13:00' }, 'al mediodía')

// --- Repeticiones ---
eq(p('tomar vitaminas todos los días a las 8'), { title: 'Tomar vitaminas', repeat: 'daily', time: '08:00', date: '2026-10-07' }, 'todos los días')
eq(p('fichar entre semana a las 7:55'), { title: 'Fichar', repeat: 'weekdays' }, 'entre semana')
eq(p('sacar al perro cada lunes'), { title: 'Sacar al perro', repeat: 'weekly', date: '2026-10-12' }, 'cada lunes')
eq(p('limpiar casa cada semana'), { title: 'Limpiar casa', repeat: 'weekly', date: '2026-10-07' }, 'cada semana')
eq(p('nómina cada mes el 28'), { title: 'Nómina', repeat: 'monthly', date: '2026-10-28' }, 'cada mes el 28')
eq(p('seguro del coche cada año el 3 de febrero'), { title: 'Seguro del coche', repeat: 'yearly', date: '2027-02-03' }, 'cada año')
eq(p('regar huerto cada 2 semanas'), { repeat: 'biweekly' }, 'cada 2 semanas')

// --- Prioridad y textos sin fecha ---
eq(p('enviar CV !alta mañana'), { title: 'Enviar CV', priority: 'alta', date: '2026-10-08' }, 'prioridad !alta')
eq(p('Recuérdame llamar a Luis mañana'), { title: 'Llamar a Luis', date: '2026-10-08' }, 'quita "recuérdame"')
eq(p('comprar leche'), { title: 'Comprar leche', date: null, time: null, repeat: null, understood: false }, 'sin fecha: texto intacto')
eq(p('leer Cien años de soledad'), { title: 'Leer Cien años de soledad', date: null }, 'no confunde "años" en un título')
eq(p('ver la serie Martes y 13'), { title: 'Ver la serie Martes y 13', date: null }, 'día de la semana en mayúscula dentro de un título: se respeta')

// --- Siguiente repetición ---
const n = (d, r, t = '2026-10-07') => nextOccurrence(d, r, t)
eq({ v: n('2026-10-07', 'daily') }, { v: '2026-10-08' }, 'diaria: día siguiente')
eq({ v: n('2026-10-09', 'weekdays') }, { v: '2026-10-12' }, 'entre semana: viernes -> lunes')
eq({ v: n('2026-10-07', 'weekly') }, { v: '2026-10-14' }, 'semanal: +7 días')
eq({ v: n('2026-10-07', 'biweekly') }, { v: '2026-10-21' }, 'cada 2 semanas: +14 días')
eq({ v: n('2026-01-31', 'monthly', '2026-01-31') }, { v: '2026-02-28' }, 'mensual 31-ene -> 28-feb')
eq({ v: n('2026-10-31', 'monthly') }, { v: '2026-11-30' }, 'mensual 31-oct -> 30-nov')
eq({ v: n('2024-02-29', 'yearly', '2024-02-29') }, { v: '2025-02-28' }, 'anual 29-feb -> 28-feb')
eq({ v: n('2026-09-01', 'weekly') }, { v: '2026-10-13' }, 'semanal atrasada: salta hasta después de hoy')
eq({ v: n('2026-10-01', 'daily') }, { v: '2026-10-08' }, 'diaria atrasada: siguiente a hoy')

if (fail) {
  console.error(`\n${fail} prueba(s) fallida(s)`)
  process.exit(1)
}
console.log('\nCaptura inteligente OK')
