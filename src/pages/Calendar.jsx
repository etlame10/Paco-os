import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Plus, CalendarDays } from 'lucide-react'
import ModuleHeader from '../components/ModuleHeader'
import ItemEditor from '../components/ItemEditor'
import { ModuleIcon, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { addDays, cx, parseISODate, toISODate, todayISO } from '../lib/utils'

const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

// Calendario unificado: muestra todo lo que tenga fecha en cualquier módulo.
export default function Calendar() {
  const { enabledModules, getModule } = useSettings()
  const { notifyError, toast } = useUI()
  const navigate = useNavigate()
  const [cursor, setCursor] = useState(() => {
    const d = new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })
  const [selected, setSelected] = useState(todayISO())
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(null)

  const calendarModules = enabledModules.filter((m) => m.showInCalendar)
  const calIds = calendarModules.map((m) => m.id).join(',')

  const gridStart = useMemo(() => {
    const dow = (cursor.getDay() + 6) % 7 // lunes = 0
    return addDays(cursor, -dow)
  }, [cursor])
  const days = useMemo(() => Array.from({ length: 42 }, (_, i) => addDays(gridStart, i)), [gridStart])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await api.items.listByDateRange(toISODate(days[0]), toISODate(days[41]))
      const ids = new Set(calIds.split(','))
      setItems(rows.filter((r) => ids.has(r.module)))
    } catch (e) {
      notifyError(e)
    } finally {
      setLoading(false)
    }
  }, [days, calIds, notifyError])

  useEffect(() => {
    load()
  }, [load])

  const byDay = useMemo(() => {
    const map = {}
    for (const it of items) (map[it.due_date] ||= []).push(it)
    return map
  }, [items])

  const monthLabel = cursor.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
  const today = todayISO()
  const selectedItems = byDay[selected] || []
  const selectedLabel = parseISODate(selected).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })

  const label = (it) => getModule(it.module)?.calendarLabel?.(it) || it.title || 'Sin título'

  return (
    <div className="page">
      <ModuleHeader
        module={{ icon: CalendarDays, color: 'var(--accent)', name: 'Calendario' }}
        title="Calendario"
        subtitle="Todo lo que tiene fecha en tus módulos: tareas, exámenes, entregas, viajes…"
      />

      <div className="calendar-layout">
        <div className="card calendar">
          <div className="calendar-head">
            <button className="icon-btn" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Mes anterior">
              <ChevronLeft size={18} />
            </button>
            <h2>{monthLabel}</h2>
            <button className="icon-btn" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Mes siguiente">
              <ChevronRight size={18} />
            </button>
            <span className="spacer" />
            <button
              className="btn ghost sm"
              onClick={() => {
                const d = new Date()
                setCursor(new Date(d.getFullYear(), d.getMonth(), 1))
                setSelected(todayISO())
              }}
            >
              Hoy
            </button>
          </div>
          <div className="calendar-grid">
            {WEEKDAYS.map((d) => (
              <div key={d} className="weekday">
                {d}
              </div>
            ))}
            {days.map((d) => {
              const iso = toISODate(d)
              const list = byDay[iso] || []
              return (
                <button
                  key={iso}
                  className={cx(
                    'day',
                    d.getMonth() !== cursor.getMonth() && 'other',
                    iso === today && 'today',
                    iso === selected && 'selected',
                  )}
                  onClick={() => setSelected(iso)}
                >
                  <span className="day-num">{d.getDate()}</span>
                  <div className="day-events">
                    {list.slice(0, 3).map((it) => {
                      const m = getModule(it.module)
                      return (
                        <span key={it.id} className={cx('day-event', it.status === 'hecha' && 'done')} style={{ '--mod': m?.color }}>
                          {label(it)}
                        </span>
                      )
                    })}
                    {list.length > 3 && <span className="day-more">+{list.length - 3}</span>}
                  </div>
                  {list.length > 0 && (
                    <div className="day-dots">
                      {list.slice(0, 4).map((it) => (
                        <i key={it.id} style={{ background: getModule(it.module)?.color }} />
                      ))}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
          {loading && <Spinner size={16} />}
        </div>

        <aside className="card day-panel">
          <header>
            <h3 className="capitalize">{selectedLabel}</h3>
          </header>
          {selectedItems.length ? (
            selectedItems.map((it) => {
              const m = getModule(it.module)
              return (
                <button key={it.id} className="widget-row widget-row-main" onClick={() => navigate(`/m/${it.module}?item=${it.id}`)}>
                  {m && <ModuleIcon module={m} size={14} />}
                  <span className={cx('ellipsis', it.status === 'hecha' && 'strike')}>{label(it)}</span>
                  <span className="meta">{m?.name}</span>
                </button>
              )
            })
          ) : (
            <p className="muted small">Nada para este día.</p>
          )}
          <div className="day-add">
            {calendarModules
              .filter((m) => m.fields?.some((f) => f.key === 'due_date'))
              .map((m) => (
                <button key={m.id} className="btn ghost xs" onClick={() => setAdding(m)}>
                  <Plus size={13} /> {m.itemName || m.name}
                </button>
              ))}
          </div>
        </aside>
      </div>

      {adding && (
        <ItemEditor
          module={adding}
          initial={{ due_date: selected }}
          onSave={async (payload) => {
            const row = await api.items.create({ module: adding.id, ...payload }).catch((e) => {
              notifyError(e)
              throw e
            })
            setItems((p) => [...p, row])
            toast('Añadido al calendario')
          }}
          onClose={() => setAdding(null)}
        />
      )}
    </div>
  )
}
