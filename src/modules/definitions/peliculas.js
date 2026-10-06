import { Film, Eye } from 'lucide-react'

export default {
  id: 'peliculas',
  name: 'Películas y series',
  description: 'Lo que quieres ver, lo que estás viendo y lo que ya has visto.',
  icon: Film,
  color: '#f43f5e',
  category: 'Ocio',
  itemName: 'título',
  layout: 'cards',
  fields: [
    { key: 'title', label: 'Título', type: 'text', required: true },
    {
      key: 'tipo', label: 'Tipo', type: 'select', default: 'pelicula',
      options: [
        { value: 'pelicula', label: 'Película' },
        { value: 'serie', label: 'Serie' },
        { value: 'documental', label: 'Documental' },
        { value: 'anime', label: 'Anime' },
      ],
    },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#64748b' },
        { value: 'viendo', label: 'Viendo', color: '#3b82f6' },
        { value: 'vista', label: 'Vista', color: '#22c55e' },
        { value: 'abandonada', label: 'Abandonada', color: '#ef4444' },
      ],
    },
    { key: 'plataforma', label: 'Plataforma', type: 'text', placeholder: 'Netflix, HBO, cine...' },
    { key: 'anio', label: 'Año', type: 'number', min: 1900, max: 2100 },
    { key: 'puntuacion', label: 'Mi puntuación', type: 'rating' },
    { key: 'tags', label: 'Géneros / etiquetas', type: 'tags' },
    { key: 'body', label: 'Opinión', type: 'textarea' },
  ],
  actions: [
    { label: 'Marcar como vista', icon: Eye, when: (i) => i.status !== 'vista', run: () => ({ status: 'vista' }) },
  ],
}
