import { StickyNote } from 'lucide-react'
import NotesView from '../views/NotesView'

export default {
  id: 'notas',
  name: 'Notas',
  description: 'Apuntes rápidos, ideas sueltas y textos largos con guardado automático.',
  icon: StickyNote,
  color: '#eab308',
  category: 'Productividad',
  defaultEnabled: true,
  component: NotesView,
  itemName: 'nota',
  fields: [
    { key: 'title', label: 'Título', type: 'text' },
    { key: 'body', label: 'Contenido', type: 'textarea' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
  ],
}
