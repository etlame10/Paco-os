import { GraduationCap } from 'lucide-react'

export default {
  id: 'estudios',
  name: 'Estudios',
  description: 'Asignaturas, exámenes, notas y progreso de cada materia.',
  icon: GraduationCap,
  color: '#7c5cff',
  category: 'Productividad',
  defaultEnabled: true,
  itemName: 'asignatura',
  layout: 'cards',
  showInCalendar: true,
  calendarLabel: (item) => `Examen: ${item.title}`,
  // Aviso del examen: por defecto a las 18:00 del día anterior.
  notifications: {
    kind: 'exam',
    time: (prefs) => prefs.examTime,
    daysBefore: (prefs) => prefs.examDaysBefore,
    active: (item) => item.status !== 'aprobada',
    message: (item, { days }) => ({
      title: `Examen: ${item.title || 'Sin título'}`,
      body: days === 0 ? 'Es hoy. ¡Mucha suerte!' : days === 1 ? 'Es mañana' : `Es dentro de ${days} días`,
    }),
  },
  fields: [
    { key: 'title', label: 'Asignatura', type: 'text', required: true, placeholder: 'Ej. Matemáticas II' },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'cursando',
      options: [
        { value: 'cursando', label: 'Cursando', color: '#3b82f6' },
        { value: 'pendiente', label: 'Pendiente', color: '#64748b' },
        { value: 'aprobada', label: 'Aprobada', color: '#22c55e' },
        { value: 'suspendida', label: 'Suspendida', color: '#ef4444' },
      ],
    },
    { key: 'profesor', label: 'Profesor/a', type: 'text' },
    { key: 'horario', label: 'Horario / aula', type: 'text', placeholder: 'Lun y Mié 10:00 · Aula 2.4' },
    { key: 'due_date', label: 'Próximo examen', type: 'date' },
    { key: 'nota', label: 'Nota', type: 'number', min: 0, max: 10, step: 0.1 },
    { key: 'progreso', label: 'Progreso del temario', type: 'progress' },
    { key: 'enlace', label: 'Enlace (aula virtual, drive...)', type: 'url' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Apuntes / notas', type: 'textarea' },
  ],
  summary: (items) => {
    const notas = items.map((i) => Number(i.data?.nota)).filter((n) => n > 0)
    const media = notas.length ? (notas.reduce((a, b) => a + b, 0) / notas.length).toFixed(2) : '—'
    return [
      { label: 'Cursando', value: items.filter((i) => i.status === 'cursando').length },
      { label: 'Aprobadas', value: items.filter((i) => i.status === 'aprobada').length },
      { label: 'Nota media', value: media },
    ]
  },
}
