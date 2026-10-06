import { Repeat, CheckCheck } from 'lucide-react'
import { todayISO, toISODate, addDays } from '../../lib/utils'

export default {
  id: 'rutinas',
  name: 'Rutinas',
  description: 'Hábitos y rutinas con seguimiento de rachas.',
  icon: Repeat,
  color: '#ec4899',
  category: 'Vida',
  itemName: 'rutina',
  layout: 'list',
  fields: [
    { key: 'title', label: 'Rutina / hábito', type: 'text', required: true, placeholder: 'Ej. Leer 20 minutos' },
    {
      key: 'frecuencia', label: 'Frecuencia', type: 'select', default: 'diaria',
      options: [
        { value: 'diaria', label: 'Diaria' },
        { value: 'semanal', label: 'Semanal' },
        { value: 'mensual', label: 'Mensual' },
      ],
    },
    {
      key: 'momento', label: 'Momento del día', type: 'select', default: 'cualquiera',
      options: [
        { value: 'manana', label: 'Mañana' },
        { value: 'tarde', label: 'Tarde' },
        { value: 'noche', label: 'Noche' },
        { value: 'cualquiera', label: 'Cuando sea' },
      ],
    },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'activa',
      options: [
        { value: 'activa', label: 'Activa', color: '#22c55e' },
        { value: 'pausada', label: 'Pausada', color: '#64748b' },
      ],
    },
    { key: 'racha', label: 'Racha (días)', type: 'number', min: 0, readOnly: true, hideInMeta: true },
    { key: 'ultima', label: 'Última vez', type: 'date', readOnly: true },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],
  actions: [
    {
      label: 'Hecho hoy',
      icon: CheckCheck,
      primary: true,
      when: (i) => i.data?.ultima !== todayISO(),
      run: (i) => {
        const yesterday = toISODate(addDays(new Date(), -1))
        const racha = i.data?.ultima === yesterday ? (Number(i.data?.racha) || 0) + 1 : 1
        return { data: { ...i.data, ultima: todayISO(), racha } }
      },
    },
  ],
  subtitle: (i) => (i.data?.racha ? `🔥 ${i.data.racha} día${i.data.racha > 1 ? 's' : ''}` : ''),
}
