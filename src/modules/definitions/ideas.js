import { Lightbulb } from 'lucide-react'

export default {
  id: 'ideas',
  name: 'Ideas',
  description: 'Captura cualquier idea antes de que se escape.',
  icon: Lightbulb,
  color: '#facc15',
  category: 'Productividad',
  itemName: 'idea',
  layout: 'cards',
  fields: [
    { key: 'title', label: 'Idea', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'nueva',
      options: [
        { value: 'nueva', label: 'Nueva', color: '#eab308' },
        { value: 'explorando', label: 'Explorando', color: '#3b82f6' },
        { value: 'hecha', label: 'Hecha realidad', color: '#22c55e' },
        { value: 'descartada', label: 'Descartada', color: '#64748b' },
      ],
    },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Desarrollo', type: 'textarea' },
  ],
}
