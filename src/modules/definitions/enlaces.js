import { Link2 } from 'lucide-react'

export default {
  id: 'enlaces',
  name: 'Enlaces',
  description: 'Tus webs, herramientas y recursos favoritos en un solo sitio.',
  icon: Link2,
  color: '#6366f1',
  category: 'Tecnología',
  itemName: 'enlace',
  layout: 'cards',
  fields: [
    { key: 'title', label: 'Nombre', type: 'text', required: true },
    { key: 'url', label: 'URL', type: 'url', required: true },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Descripción', type: 'textarea' },
  ],
  openUrlField: 'url',
}
