import { ModuleIcon } from './ui'

export default function ModuleHeader({ module, title, subtitle, actions }) {
  return (
    <header className="page-header">
      <div className="page-title">
        {module && <ModuleIcon module={module} size={22} />}
        <div>
          <h1>{title || module?.name}</h1>
          {(subtitle || module?.description) && <p className="muted">{subtitle || module.description}</p>}
        </div>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function SummaryChips({ stats }) {
  if (!stats?.length) return null
  return (
    <div className="stats-row">
      {stats.map((s) => (
        <div key={s.label} className="stat">
          <span className="stat-value">{s.value}</span>
          <span className="stat-label">{s.label}</span>
        </div>
      ))}
    </div>
  )
}
