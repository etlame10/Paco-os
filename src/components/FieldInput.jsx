import { useState } from 'react'
import { X } from 'lucide-react'
import { Rating } from './ui'

// Renderiza el control adecuado según el tipo de campo de un módulo.
// Tipos: text, textarea, number, money, date, time, datetime, select, rating, url, checkbox, tags, progress
export default function FieldInput({ field, value, onChange, autoFocus }) {
  const common = {
    id: `f-${field.key}`,
    autoFocus,
    disabled: field.readOnly,
    placeholder: field.placeholder,
  }

  switch (field.type) {
    case 'textarea':
      return <textarea {...common} rows={field.rows || 5} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'number':
    case 'money':
      return (
        <div className={field.type === 'money' ? 'input-affix' : undefined}>
          <input
            {...common}
            type="number"
            inputMode="decimal"
            min={field.min}
            max={field.max}
            step={field.step ?? (field.type === 'money' ? 0.01 : 'any')}
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          />
          {field.type === 'money' && <span>€</span>}
        </div>
      )
    case 'date':
      return <input {...common} type="date" value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'time':
      return <input {...common} type="time" value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'datetime':
      return <input {...common} type="datetime-local" value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'url':
      return <input {...common} type="url" inputMode="url" placeholder={field.placeholder || 'https://'} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    case 'select':
      return (
        <select {...common} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
          {!field.default && <option value="">{field.emptyLabel || '—'}</option>}
          {field.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )
    case 'rating':
      return <Rating value={Number(value) || 0} onChange={onChange} size={22} />
    case 'checkbox':
      return (
        <label className="switch">
          <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          <span />
        </label>
      )
    case 'progress':
      return (
        <div className="range-row">
          <input type="range" min={0} max={100} step={5} value={Number(value) || 0} onChange={(e) => onChange(Number(e.target.value))} />
          <span className="range-value">{Number(value) || 0}%</span>
        </div>
      )
    case 'tags':
      return <TagsInput value={value || []} onChange={onChange} placeholder={field.placeholder} />
    default:
      return <input {...common} type="text" value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
  }
}

function TagsInput({ value, onChange, placeholder = 'Escribe y pulsa Enter' }) {
  const [text, setText] = useState('')
  const add = () => {
    const t = text.trim().replace(/^#/, '').replace(/,$/, '')
    if (t && !value.includes(t)) onChange([...value, t])
    setText('')
  }
  return (
    <div className="tags-input">
      {value.map((t) => (
        <span key={t} className="tag">
          #{t}
          <button type="button" onClick={() => onChange(value.filter((x) => x !== t))} aria-label={`Quitar ${t}`}>
            <X size={12} />
          </button>
        </span>
      ))}
      <input
        value={text}
        placeholder={value.length ? '' : placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add()
          } else if (e.key === 'Backspace' && !text && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={add}
      />
    </div>
  )
}
