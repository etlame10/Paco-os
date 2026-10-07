import { Calendar, Clock, Repeat, Flag, ArrowRight, Sparkles } from 'lucide-react'
import { REPEAT_LABELS } from '../lib/smart/recurrence'
import { formatDate, relativeDay } from '../lib/utils'

// Muestra lo que la captura inteligente ha entendido antes de guardar.
export default function SmartHint({ parsed, target, showTitle = true }) {
  if (!parsed?.understood) return null
  const rel = parsed.date ? relativeDay(parsed.date) : ''
  const abs = parsed.date ? formatDate(parsed.date) : ''
  return (
    <div className="smart-hint" aria-live="polite">
      <Sparkles size={13} className="accent-text" />
      {showTitle && <strong className="ellipsis">{parsed.title}</strong>}
      {parsed.date && (
        <span className="chip">
          <Calendar size={12} /> {rel === abs ? abs : `${rel} · ${abs}`}
        </span>
      )}
      {parsed.time && (
        <span className="chip">
          <Clock size={12} /> {parsed.time}
        </span>
      )}
      {parsed.repeat && (
        <span className="chip">
          <Repeat size={12} /> {REPEAT_LABELS[parsed.repeat]}
        </span>
      )}
      {parsed.priority && (
        <span className="chip">
          <Flag size={12} /> {parsed.priority}
        </span>
      )}
      {target && (
        <span className="chip target">
          <ArrowRight size={12} /> {target.name}
        </span>
      )}
    </div>
  )
}
