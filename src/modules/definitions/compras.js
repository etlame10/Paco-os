import { ShoppingCart, Check } from 'lucide-react'
import { formatMoney } from '../../lib/utils'

export default {
  id: 'compras',
  name: 'Compras',
  description: 'Lista de la compra y cosas que quieres comprar, con precios.',
  icon: ShoppingCart,
  color: '#14b8a6',
  category: 'Vida',
  itemName: 'artículo',
  layout: 'list',
  fields: [
    { key: 'title', label: 'Artículo', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#f59e0b' },
        { value: 'comprado', label: 'Comprado', color: '#22c55e' },
      ],
    },
    { key: 'cantidad', label: 'Cantidad', type: 'number', min: 0 },
    { key: 'precio', label: 'Precio (unidad)', type: 'money' },
    { key: 'tienda', label: 'Tienda', type: 'text' },
    { key: 'enlace', label: 'Enlace', type: 'url' },
    { key: 'tags', label: 'Categorías', type: 'tags' },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],
  actions: [
    { label: 'Marcar comprado', icon: Check, when: (i) => i.status !== 'comprado', run: () => ({ status: 'comprado' }) },
  ],
  summary: (items) => {
    const pend = items.filter((i) => i.status !== 'comprado')
    const total = pend.reduce((a, i) => a + (Number(i.data?.precio) || 0) * (Number(i.data?.cantidad) || 1), 0)
    return [
      { label: 'Pendientes', value: pend.length },
      { label: 'Total pendiente', value: formatMoney(total) },
    ]
  },
}
