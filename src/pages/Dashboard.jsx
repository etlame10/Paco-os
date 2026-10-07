import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CalendarDays, CheckSquare, Pin, Clock, Zap, LayoutGrid, Plus, ChevronRight, FolderOpen, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { ModuleIcon, Spinner } from '../components/ui'
import SmartHint from '../components/SmartHint'
import { parseQuick } from '../lib/smart/parseQuick'
import { autoModule, buildCaptureItem, moduleAcceptsSchedule } from '../lib/smart/capture'
import { addDays, cx, daysUntil, formatBytes, greeting, relativeDay, timeAgo, toISODate, todayISO } from '../lib/utils'

export default function Dashboard() {
  const { user } = useAuth()
  const { settings, enabledModules, getModule } = useSettings()
  const { notifyError, toast } = useUI()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [now, setNow] = useState(new Date())

  const itemModules = enabledModules.filter((m) => m.usesItems !== false)
  const [captureText, setCaptureText] = useState('')
  const [captureModule, setCaptureModule] = useState('auto')
  // Captura inteligente: entiende fechas, horas y repeticiones ("dentista mañana a las 17:30").
  const parsed = useMemo(() => parseQuick(captureText), [captureText])
  const captureTarget =
    captureModule === 'auto' ? autoModule(parsed, itemModules) : getModule(captureModule) || itemModules[0]
  const showHint = captureText.trim() && parsed.understood && moduleAcceptsSchedule(captureTarget)

  const load = useCallback(async () => {
    try {
      const [it, fs] = await Promise.all([api.items.list(), api.files.list().catch(() => [])])
      setItems(it)
      setFiles(fs)
    } catch (e) {
      notifyError(e)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    load()
    const t = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(t)
  }, [load])

  const enabledIds = new Set(enabledModules.map((m) => m.id))
  const mine = items.filter((i) => enabledIds.has(i.module))

  const todayTasks = useMemo(
    () =>
      mine
        .filter((i) => i.module === 'tareas' && i.status !== 'hecha' && i.due_date && daysUntil(i.due_date) <= 0)
        .sort((a, b) => a.due_date.localeCompare(b.due_date)),
    [mine],
  )

  const upcoming = useMemo(() => {
    const to = toISODate(addDays(new Date(), 14))
    const today = todayISO()
    return mine
      .filter((i) => {
        const m = getModule(i.module)
        if (!m?.showInCalendar || !i.due_date) return false
        // Lo ya completado (tareas hechas, avisos hechos...) no aparece como próximo.
        if (m.recurrence ? i.status === m.recurrence.doneStatus : i.module === 'tareas' && i.status === 'hecha') return false
        return i.due_date > today && i.due_date <= to
      })
      .sort((a, b) => a.due_date.localeCompare(b.due_date))
      .slice(0, 8)
  }, [mine, getModule])

  const pinned = mine.filter((i) => i.pinned).slice(0, 8)
  const recent = [...mine].sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1)).slice(0, 6)

  const name = settings.displayName || user?.email?.split('@')[0] || ''
  const dateStr = now.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })
  const timeStr = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })

  const capture = async (e) => {
    e.preventDefault()
    const title = captureText.trim()
    if (!title || !captureTarget) return
    try {
      const base = buildCaptureItem(parseQuick(title), captureTarget, title)
      const row = await api.items.create({ module: captureTarget.id, ...base })
      setItems((p) => [row, ...p])
      setCaptureText('')
      toast(row.due_date ? `Guardado en ${captureTarget.name} · ${relativeDay(row.due_date)}` : `Guardado en ${captureTarget.name}`)
    } catch (err) {
      notifyError(err)
    }
  }

  const completeTask = async (t) => {
    setItems((p) => p.map((i) => (i.id === t.id ? { ...i, status: 'hecha' } : i)))
    try {
      await api.items.update(t.id, { status: 'hecha' })
    } catch (e) {
      notifyError(e)
      load()
    }
  }

  const openItem = (i) => navigate(`/m/${i.module}?item=${i.id}`)

  return (
    <div className="page dashboard">
      <section className="hero">
        <div>
          <p className="hero-date">{dateStr}</p>
          <h1>
            {greeting()}
            {name && `, ${name}`} 👋
          </h1>
          <p className="muted">
            {todayTasks.length
              ? `Tienes ${todayTasks.length} tarea${todayTasks.length > 1 ? 's' : ''} para hoy.`
              : 'Nada urgente para hoy. Buen momento para avanzar en tus cosas.'}
          </p>
        </div>
        <div className="hero-clock">{timeStr}</div>
      </section>

      {itemModules.length > 0 && (
        <form className="quick-add capture" onSubmit={capture}>
          <Zap size={18} className="accent-text" />
          <input
            value={captureText}
            onChange={(e) => setCaptureText(e.target.value)}
            placeholder="Escribe lo que sea: «dentista mañana a las 17:30», «gimnasio cada lunes»…"
            aria-label="Captura rápida"
          />
          <select value={captureModule} onChange={(e) => setCaptureModule(e.target.value)} aria-label="Módulo de destino">
            <option value="auto">✨ Automático</option>
            {itemModules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <button className="btn primary sm" disabled={!captureText.trim()}>
            Guardar
          </button>
          {showHint && <SmartHint parsed={parsed} target={captureTarget} />}
        </form>
      )}

      {loading ? (
        <Spinner label="Preparando tu panel…" />
      ) : (
        <div className="widgets">
          {enabledIds.has('tareas') && (
            <Widget title="Hoy" icon={CheckSquare} link="/m/tareas" linkText="Ver tareas">
              {todayTasks.length ? (
                todayTasks.map((t) => (
                  <div key={t.id} className="widget-row">
                    <button className="check" onClick={() => completeTask(t)} aria-label="Completar" />
                    <button className="widget-row-main" onClick={() => openItem(t)}>
                      <span className="ellipsis">{t.title}</span>
                      <span className={cx('meta due', daysUntil(t.due_date) < 0 && 'overdue')}>{relativeDay(t.due_date)}</span>
                    </button>
                  </div>
                ))
              ) : (
                <WidgetEmpty text="Sin tareas para hoy 🎉" />
              )}
            </Widget>
          )}

          <Widget title="Próximos 14 días" icon={CalendarDays} link="/calendario" linkText="Calendario">
            {upcoming.length ? (
              upcoming.map((i) => <ItemLine key={i.id} item={i} module={getModule(i.module)} onClick={() => openItem(i)} right={relativeDay(i.due_date)} />)
            ) : (
              <WidgetEmpty text="Nada programado. Añade fechas a tus tareas, exámenes o viajes." />
            )}
          </Widget>

          <Widget title="Fijados" icon={Pin}>
            {pinned.length ? (
              pinned.map((i) => <ItemLine key={i.id} item={i} module={getModule(i.module)} onClick={() => openItem(i)} />)
            ) : (
              <WidgetEmpty text="Fija elementos importantes con el icono 📌 para tenerlos siempre aquí." />
            )}
          </Widget>

          <Widget title="Actividad reciente" icon={Clock}>
            {recent.length ? (
              recent.map((i) => <ItemLine key={i.id} item={i} module={getModule(i.module)} onClick={() => openItem(i)} right={timeAgo(i.updated_at)} />)
            ) : (
              <WidgetEmpty text="Aquí verás lo último que has tocado." />
            )}
          </Widget>

          {enabledIds.has('archivos') && (
            <Widget title="Archivos recientes" icon={FolderOpen} link="/m/archivos" linkText="Abrir">
              {files.length ? (
                files.slice(0, 5).map((f) => (
                  <Link key={f.id} to="/m/archivos" className="widget-row widget-row-main">
                    <span className="ellipsis">{f.name}</span>
                    <span className="meta">{formatBytes(f.size)}</span>
                  </Link>
                ))
              ) : (
                <WidgetEmpty text="Sube tus primeros documentos." />
              )}
            </Widget>
          )}
        </div>
      )}

      <section className="launcher-section">
        <div className="section-head">
          <h2>
            <LayoutGrid size={18} /> Mis módulos
          </h2>
          <Link to="/modulos" className="btn ghost sm">
            <Plus size={15} /> Añadir módulos
          </Link>
        </div>
        <div className="launcher">
          {enabledModules.map((m) => {
            const count = m.usesItems === false ? files.length : items.filter((i) => i.module === m.id).length
            return (
              <Link key={m.id} to={`/m/${m.id}`} className="launcher-tile" style={{ '--mod': m.color }}>
                <ModuleIcon module={m} size={22} />
                <strong>{m.name}</strong>
                <span className="muted small">{count} {count === 1 ? 'elemento' : 'elementos'}</span>
              </Link>
            )
          })}
          <Link to="/modulos" className="launcher-tile add">
            <span className="module-icon">
              <Sparkles size={22} />
            </span>
            <strong>Más módulos</strong>
            <span className="muted small">Activa o crea los tuyos</span>
          </Link>
        </div>
      </section>
    </div>
  )
}

function Widget({ title, icon: Icon, link, linkText, children }) {
  return (
    <section className="card widget">
      <header>
        <h3>
          <Icon size={16} /> {title}
        </h3>
        {link && (
          <Link to={link} className="widget-link">
            {linkText} <ChevronRight size={14} />
          </Link>
        )}
      </header>
      <div className="widget-body">{children}</div>
    </section>
  )
}

function WidgetEmpty({ text }) {
  return <p className="muted small widget-empty">{text}</p>
}

function ItemLine({ item, module, onClick, right }) {
  if (!module) return null
  return (
    <button className="widget-row widget-row-main" onClick={onClick}>
      <ModuleIcon module={module} size={14} />
      <span className="ellipsis">{item.title || 'Sin título'}</span>
      {right && <span className="meta">{right}</span>}
    </button>
  )
}
