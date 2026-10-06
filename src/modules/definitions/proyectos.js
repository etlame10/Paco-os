import { Rocket } from 'lucide-react'

export default {
  id: 'proyectos',
  name: 'Proyectos',
  description: 'Tablero kanban para tus proyectos personales y su progreso.',
  icon: Rocket,
  color: '#f97316',
  category: 'Productividad',
  itemName: 'proyecto',
  layout: 'board',
  showInCalendar: true,
  calendarLabel: (item) => `Entrega: ${item.title}`,
  fields: [
    { key: 'title', label: 'Proyecto', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'idea',
      options: [
        { value: 'idea', label: 'Idea', color: '#a855f7' },
        { value: 'en-curso', label: 'En curso', color: '#3b82f6' },
        { value: 'pausado', label: 'Pausado', color: '#f59e0b' },
        { value: 'terminado', label: 'Terminado', color: '#22c55e' },
      ],
    },
    { key: 'due_date', label: 'Fecha límite', type: 'date' },
    { key: 'progreso', label: 'Progreso', type: 'progress' },
    { key: 'enlace', label: 'Enlace / repositorio', type: 'url' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Descripción y próximos pasos', type: 'textarea' },
  ],
}
