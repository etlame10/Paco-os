import { CheckSquare } from 'lucide-react'
import TasksView from '../views/TasksView'
import { REPEAT_OPTIONS } from '../../lib/smart/recurrence'

export default {
  id: 'tareas',
  name: 'Tareas',
  description: 'Pendientes del día a día con prioridad y fecha límite.',
  icon: CheckSquare,
  color: '#22c55e',
  category: 'Productividad',
  defaultEnabled: true,
  component: TasksView,
  itemName: 'tarea',
  showInCalendar: true,
  // Al completar una tarea que se repite, se crea la siguiente automáticamente.
  recurrence: { doneStatus: 'hecha', openStatus: 'pendiente' },
  // Aviso a la hora configurada (09:00 por defecto) del día límite, solo si sigue pendiente.
  notifications: {
    kind: 'task',
    time: (prefs) => prefs.taskTime,
    daysBefore: () => 0,
    active: (item) => item.status !== 'hecha',
    message: (item, { days }) => ({
      title: `Tarea: ${item.title || 'Sin título'}`,
      body: !item.due_date ? 'Recordatorio' : days === 0 ? 'Vence hoy' : days === 1 ? 'Vence mañana' : `Vence en ${days} días`,
    }),
  },
  fields: [
    { key: 'title', label: 'Tarea', type: 'text', required: true, placeholder: '¿Qué hay que hacer?' },
    {
      key: 'priority', label: 'Prioridad', type: 'select', default: 'media',
      options: [
        { value: 'alta', label: 'Alta', color: '#ef4444' },
        { value: 'media', label: 'Media', color: '#f59e0b' },
        { value: 'baja', label: 'Baja', color: '#64748b' },
      ],
    },
    { key: 'due_date', label: 'Fecha límite', type: 'date' },
    { key: 'repeat', label: 'Repetir', type: 'select', emptyLabel: 'No se repite', options: REPEAT_OPTIONS },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#3b82f6' },
        { value: 'hecha', label: 'Hecha', color: '#22c55e' },
      ],
    },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],
}
