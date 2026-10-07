import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Search, LayoutDashboard, CalendarDays, Settings, Puzzle, Plus, CornerDownLeft } from 'lucide-react'
import { api } from '../lib/api'
import { useSettings } from '../context/SettingsContext'
import { ModuleIcon } from './ui'
import { cx } from '../lib/utils'

// Buscador global (Ctrl/Cmd + K): navega a módulos y busca en todos tus elementos.
export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate()
  const { enabledModules, getModule } = useSettings()
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) {
      setQ('')
      setResults([])
      setActive(0)
    }
  }, [open])

  useEffect(() => {
    if (!q.trim()) return setResults([])
    const t = setTimeout(() => {
      api.items
        .search(q)
        .then((r) => setResults(r.filter((i) => enabledModules.some((m) => m.id === i.module))))
        .catch(() => setResults([]))
    }, 200)
    return () => clearTimeout(t)
  }, [q, enabledModules])

  const commands = useMemo(() => {
    const base = [
      { id: 'home', label: 'Inicio', icon: LayoutDashboard, to: '/' },
      { id: 'cal', label: 'Calendario', icon: CalendarDays, to: '/calendario' },
      ...enabledModules.map((m) => ({ id: m.id, label: m.name, module: m, to: `/m/${m.id}` })),
      ...enabledModules
        .filter((m) => m.usesItems !== false)
        .map((m) => ({ id: `new-${m.id}`, label: `${/a$/.test(m.itemName || '') ? 'Nueva' : 'Nuevo'} ${m.itemName || 'elemento'} en ${m.name}`, icon: Plus, to: `/m/${m.id}?new=1` })),
      { id: 'mods', label: 'Módulos', icon: Puzzle, to: '/modulos' },
      { id: 'settings', label: 'Ajustes', icon: Settings, to: '/ajustes' },
    ]
    const t = q.toLowerCase().trim()
    const cmds = t ? base.filter((c) => c.label.toLowerCase().includes(t)) : base.slice(0, 2 + enabledModules.length)
    const items = results.map((i) => ({ id: i.id, label: i.title || 'Sin título', module: getModule(i.module), to: `/m/${i.module}?item=${i.id}`, isItem: true }))
    return [...cmds, ...items]
  }, [q, results, enabledModules, getModule])

  useEffect(() => setActive(0), [q])

  if (!open) return null

  const go = (c) => {
    navigate(c.to)
    onClose()
  }

  return createPortal(
    <div className="modal-backdrop palette-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-label="Buscar">
        <div className="palette-input">
          <Search size={18} />
          <input
            ref={inputRef}
            autoFocus
            value={q}
            placeholder="Buscar en PACO OS…"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') onClose()
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setActive((a) => Math.min(a + 1, commands.length - 1))
              }
              if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((a) => Math.max(a - 1, 0))
              }
              if (e.key === 'Enter' && commands[active]) go(commands[active])
            }}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="palette-results">
          {commands.map((c, i) => (
            <button key={c.id} className={cx('palette-item', i === active && 'active')} onMouseEnter={() => setActive(i)} onClick={() => go(c)}>
              {c.module ? <ModuleIcon module={c.module} size={14} /> : <span className="module-icon plain">{c.icon && <c.icon size={14} />}</span>}
              <span className="ellipsis">{c.label}</span>
              {c.isItem && <span className="meta">{c.module?.name}</span>}
              {i === active && <CornerDownLeft size={14} className="muted" />}
            </button>
          ))}
          {q && !commands.length && <p className="muted small palette-empty">Sin resultados para "{q}"</p>}
        </div>
      </div>
    </div>,
    document.body,
  )
}
