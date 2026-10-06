import { FolderOpen } from 'lucide-react'
import FilesView from '../views/FilesView'

export default {
  id: 'archivos',
  name: 'Archivos',
  description: 'Tus documentos, imágenes y PDFs en la nube, organizados por carpetas.',
  icon: FolderOpen,
  color: '#06b6d4',
  category: 'Productividad',
  defaultEnabled: true,
  component: FilesView,
  usesItems: false,
}
