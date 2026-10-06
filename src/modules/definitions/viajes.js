import { Plane } from 'lucide-react'

export default {
  id: 'viajes',
  name: 'Viajes',
  description: 'Destinos soñados, viajes planificados y recuerdos.',
  icon: Plane,
  color: '#0ea5e9',
  category: 'Vida',
  itemName: 'viaje',
  layout: 'cards',
  showInCalendar: true,
  calendarLabel: (item) => `Viaje: ${item.title}`,
  fields: [
    { key: 'title', label: 'Destino', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'idea',
      options: [
        { value: 'idea', label: 'Idea', color: '#a855f7' },
        { value: 'planificando', label: 'Planificando', color: '#f59e0b' },
        { value: 'reservado', label: 'Reservado', color: '#3b82f6' },
        { value: 'realizado', label: 'Realizado', color: '#22c55e' },
      ],
    },
    { key: 'due_date', label: 'Salida', type: 'date' },
    { key: 'vuelta', label: 'Vuelta', type: 'date' },
    { key: 'presupuesto', label: 'Presupuesto', type: 'money' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Itinerario, reservas, notas', type: 'textarea' },
  ],
}
