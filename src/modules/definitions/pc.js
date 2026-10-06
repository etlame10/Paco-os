import { Monitor } from 'lucide-react'
import { formatMoney } from '../../lib/utils'

export default {
  id: 'pc',
  name: 'Mi PC',
  description: 'Componentes, periféricos, software, licencias y mejoras pendientes.',
  icon: Monitor,
  color: '#3b82f6',
  category: 'Tecnología',
  itemName: 'elemento',
  layout: 'list',
  fields: [
    { key: 'title', label: 'Nombre', type: 'text', required: true, placeholder: 'Ej. RTX 4070' },
    {
      key: 'categoria', label: 'Categoría', type: 'select', default: 'componente',
      options: [
        { value: 'cpu', label: 'CPU' },
        { value: 'gpu', label: 'Gráfica' },
        { value: 'ram', label: 'RAM' },
        { value: 'almacenamiento', label: 'Almacenamiento' },
        { value: 'placa', label: 'Placa base' },
        { value: 'fuente', label: 'Fuente' },
        { value: 'periferico', label: 'Periférico' },
        { value: 'software', label: 'Software / licencia' },
        { value: 'componente', label: 'Otro componente' },
      ],
    },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'instalado',
      options: [
        { value: 'instalado', label: 'Instalado', color: '#22c55e' },
        { value: 'deseado', label: 'Lo quiero', color: '#a855f7' },
        { value: 'pedido', label: 'Pedido', color: '#f59e0b' },
        { value: 'retirado', label: 'Retirado / vendido', color: '#64748b' },
      ],
    },
    { key: 'modelo', label: 'Modelo / detalles', type: 'text' },
    { key: 'precio', label: 'Precio', type: 'money' },
    { key: 'garantia', label: 'Fin de garantía', type: 'date' },
    { key: 'enlace', label: 'Enlace', type: 'url' },
    { key: 'body', label: 'Notas (claves, configuración...)', type: 'textarea' },
  ],
  summary: (items) => [
    { label: 'Instalados', value: items.filter((i) => i.status === 'instalado').length },
    {
      label: 'Valor del equipo',
      value: formatMoney(items.filter((i) => i.status === 'instalado').reduce((a, i) => a + (Number(i.data?.precio) || 0), 0)),
    },
  ],
}
