import { Gamepad2 } from 'lucide-react'

export default {
  id: 'juegos',
  name: 'Juegos',
  description: 'Tu backlog de videojuegos, horas jugadas y valoraciones.',
  icon: Gamepad2,
  color: '#a855f7',
  category: 'Ocio',
  itemName: 'juego',
  layout: 'cards',
  fields: [
    { key: 'title', label: 'Juego', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#64748b' },
        { value: 'jugando', label: 'Jugando', color: '#3b82f6' },
        { value: 'completado', label: 'Completado', color: '#22c55e' },
        { value: 'abandonado', label: 'Abandonado', color: '#ef4444' },
      ],
    },
    {
      key: 'plataforma', label: 'Plataforma', type: 'select', default: 'pc',
      options: [
        { value: 'pc', label: 'PC' },
        { value: 'ps5', label: 'PlayStation' },
        { value: 'xbox', label: 'Xbox' },
        { value: 'switch', label: 'Switch' },
        { value: 'movil', label: 'Móvil' },
        { value: 'otra', label: 'Otra' },
      ],
    },
    { key: 'horas', label: 'Horas jugadas', type: 'number', min: 0 },
    { key: 'puntuacion', label: 'Mi puntuación', type: 'rating' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],
  summary: (items) => [
    { label: 'Jugando', value: items.filter((i) => i.status === 'jugando').length },
    { label: 'Completados', value: items.filter((i) => i.status === 'completado').length },
    { label: 'Horas totales', value: items.reduce((a, i) => a + (Number(i.data?.horas) || 0), 0) },
  ],
}
