// Pequeños componentes de interfaz reutilizables por todos los módulos.
import { Star, Loader2 } from 'lucide-react'
import { cx } from '../lib/utils'

export function Spinner({ size = 20, label }) {
  return (
    <div className="spinner-wrap">
      <Loader2 size={size} className="spin" />
      {label && <span>{label}</span>}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="empty">
      {Icon && (
        <div className="empty-icon">
          <Icon size={28} />
        </div>
      )}
      <h3>{title}</h3>
      {text && <p className="muted">{text}</p>}
      {action}
    </div>
  )
}

export function Badge({ color, children, className }) {
  return (
    <span className={cx('badge', className)} style={color ? { '--badge': color } : undefined}>
      {children}
    </span>
  )
}

export function Rating({ value = 0, onChange, size = 16 }) {
  return (
    <div className={cx('rating', onChange && 'editable')}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={!onChange}
          onClick={() => onChange?.(n === value ? 0 : n)}
          aria-label={`${n} estrellas`}
        >
          <Star size={size} className={n <= value ? 'on' : ''} />
        </button>
      ))}
    </div>
  )
}

export function Progress({ value = 0, color }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="progress" title={`${v}%`}>
      <div style={{ width: `${v}%`, background: color }} />
    </div>
  )
}

export function Tags({ tags }) {
  if (!tags?.length) return null
  return (
    <div className="tags">
      {tags.map((t) => (
        <span key={t} className="tag">
          #{t}
        </span>
      ))}
    </div>
  )
}

export function ModuleIcon({ module, size = 18, box = true }) {
  const Icon = module.icon
  if (!box) return <Icon size={size} style={{ color: module.color }} />
  return (
    <span className="module-icon" style={{ '--mod': module.color }}>
      <Icon size={size} />
    </span>
  )
}

export function Segmented({ value, onChange, options }) {
  return (
    <div className="segmented">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={cx(value === o.value && 'active')}
          onClick={() => onChange(o.value)}
          title={o.title || o.label}
        >
          {o.icon && <o.icon size={15} />}
          {o.label && <span>{o.label}</span>}
        </button>
      ))}
    </div>
  )
}
