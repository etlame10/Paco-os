import { Wallet } from 'lucide-react'
import { formatMoney, todayISO } from '../../lib/utils'

export default {
  id: 'finanzas',
  name: 'Finanzas',
  description: 'Ingresos y gastos con balance mensual.',
  icon: Wallet,
  color: '#10b981',
  category: 'Vida',
  itemName: 'movimiento',
  layout: 'list',
  sortDefault: 'due_date',
  showInCalendar: false,
  fields: [
    { key: 'title', label: 'Concepto', type: 'text', required: true },
    {
      key: 'status', label: 'Tipo', type: 'select', default: 'gasto',
      options: [
        { value: 'gasto', label: 'Gasto', color: '#ef4444' },
        { value: 'ingreso', label: 'Ingreso', color: '#22c55e' },
      ],
    },
    { key: 'importe', label: 'Importe', type: 'money', required: true, hideInMeta: true },
    { key: 'due_date', label: 'Fecha', type: 'date', default: () => todayISO() },
    {
      key: 'categoria', label: 'Categoría', type: 'select', default: 'otros',
      options: [
        { value: 'casa', label: 'Casa' },
        { value: 'comida', label: 'Comida' },
        { value: 'transporte', label: 'Transporte' },
        { value: 'ocio', label: 'Ocio' },
        { value: 'suscripciones', label: 'Suscripciones' },
        { value: 'estudios', label: 'Estudios' },
        { value: 'salud', label: 'Salud' },
        { value: 'nomina', label: 'Nómina' },
        { value: 'otros', label: 'Otros' },
      ],
    },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],
  subtitle: (i) => `${i.status === 'ingreso' ? '+' : '−'}${formatMoney(i.data?.importe)}`,
  summary: (items) => {
    const month = todayISO().slice(0, 7)
    const sum = (arr, t) => arr.filter((i) => i.status === t).reduce((a, i) => a + (Number(i.data?.importe) || 0), 0)
    const thisMonth = items.filter((i) => (i.due_date || i.created_at || '').startsWith(month))
    const ing = sum(thisMonth, 'ingreso')
    const gas = sum(thisMonth, 'gasto')
    return [
      { label: 'Ingresos (mes)', value: formatMoney(ing) },
      { label: 'Gastos (mes)', value: formatMoney(gas) },
      { label: 'Balance (mes)', value: formatMoney(ing - gas) },
      { label: 'Balance total', value: formatMoney(sum(items, 'ingreso') - sum(items, 'gasto')) },
    ]
  },
}
