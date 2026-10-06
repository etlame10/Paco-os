import { ExternalLink } from 'lucide-react'
import { Badge, Progress, Rating } from './ui'
import { formatDate, formatMoney } from '../lib/utils'
import { optionLabel } from '../lib/items'

export function hasValue(v) {
  return !(v === '' || v === null || v === undefined || (Array.isArray(v) && !v.length))
}

// Muestra el valor de un campo de forma compacta en tarjetas y listas.
export default function FieldValue({ field, value, color }) {
  if (!hasValue(value)) return null
  switch (field.type) {
    case 'select': {
      const opt = field.options.find((o) => o.value === value)
      return <Badge color={opt?.color}>{optionLabel(field, value)}</Badge>
    }
    case 'money':
      return <span className="meta">{formatMoney(value)}</span>
    case 'date':
      return (
        <span className="meta">
          {field.label}: {formatDate(value)}
        </span>
      )
    case 'rating':
      return Number(value) > 0 ? <Rating value={Number(value)} size={13} /> : null
    case 'progress':
      return <Progress value={value} color={color} />
    case 'url': {
      let host = value
      try {
        host = new URL(value).hostname.replace(/^www\./, '')
      } catch {
        /* url no válida: se muestra tal cual */
      }
      return (
        <a className="meta link" href={value} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
          <ExternalLink size={12} /> {host}
        </a>
      )
    }
    case 'checkbox':
      return value ? <span className="meta">{field.label}</span> : null
    case 'number':
      return (
        <span className="meta">
          {field.label}: {value}
        </span>
      )
    default:
      return <span className="meta">{String(value)}</span>
  }
}
