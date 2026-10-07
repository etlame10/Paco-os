import { BellRing, Check } from 'lucide-react'

// Recordatorios sueltos con fecha y hora ("llamar al médico a las 17:30").
export default {
  id: 'avisos',
  name: 'Avisos',
  description: 'Recordatorios personalizados con fecha y hora que te llegan como notificación.',
  icon: BellRing,
  color: '#f43f5e',
  category: 'Productividad',
  defaultEnabled: true,
  itemName: 'aviso',
  layout: 'list',
  sortDefault: 'due_date',
  showInCalendar: true,
  calendarLabel: (item) => `${item.data?.hora ? item.data.hora + ' · ' : ''}${item.title}`,
  notifications: {
    kind: 'custom',
    time: (prefs, item) => item.data?.hora || '09:00',
    daysBefore: () => 0,
    active: (item) => item.status !== 'hecho',
    message: (item) => ({ title: item.title || 'Aviso', body: item.body?.slice(0, 140) || 'Recordatorio de PACO OS' }),
  },
  fields: [
    { key: 'title', label: 'Aviso', type: 'text', required: true, placeholder: 'Ej. Llamar al dentista' },
    { key: 'due_date', label: 'Fecha', type: 'date', required: true },
    { key: 'hora', label: 'Hora', type: 'time', default: '09:00', hideInMeta: false },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#f43f5e' },
        { value: 'hecho', label: 'Hecho', color: '#22c55e' },
      ],
    },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Detalles', type: 'textarea' },
  ],
  actions: [
    { label: 'Hecho', icon: Check, when: (i) => i.status !== 'hecho', run: () => ({ status: 'hecho' }) },
  ],
}
