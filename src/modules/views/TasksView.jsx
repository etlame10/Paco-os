import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, Calendar, Flag, Trash2, CheckSquare, Repeat } from 'lucide-react'
import ModuleHeader from '../../components/ModuleHeader'
import ItemEditor from '../../components/ItemEditor'
import { EmptyState, Segmented, Spinner, Tags } from '../../components/ui'
import { useItems } from '../../hooks/useItems'
import { useUI } from '../../context/UIContext'
import { cx, daysUntil, relativeDay, todayISO } from '../../lib/utils'
import SmartHint from '../../components/SmartHint'
import { parseQuick } from '../../lib/smart/parseQuick'
import { buildCaptureItem } from '../../lib/smart/capture'
import { REPEAT_LABELS } from '../../lib/smart/recurrence'

const PRIORITY = { alta: 0, media: 1, baja: 2 }
const PRIORITY_COLOR = { alta: '#ef4444', media: '#f59e0b', baja: '#64748b' }

export default function TasksView({ module }) {
  const { items, loading, create, update, remove } = useItems(module.id)
  const { confirm, toast } = useUI()
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState('pendientes')
  const [text, setText] = useState('')
  const [quickDate, setQuickDate] = useState('')
  const [editing, setEditing] = useState(null)
  const parsed = useMemo(() => parseQuick(text), [text])

  useEffect(() => {
    const id = params.get('item')
    if (id && !loading) {
      const it = items.find((i) => i.id === id)
      if (it) setEditing(it)
      params.delete('item')
      setParams(params, { replace: true })
    }
    if (params.get('new') === '1') {
      setEditing('new')
      params.delete('new')
      setParams(params, { replace: true })
    }
  }, [params, items, loading, setParams])

  const isDone = (t) => t.status === 'hecha'

  const sorted = useMemo(
    () =>
      [...items].sort(
        (a, b) =>
          (a.due_date || '9999').localeCompare(b.due_date || '9999') ||
          (PRIORITY[a.data?.priority] ?? 1) - (PRIORITY[b.data?.priority] ?? 1),
      ),
    [items],
  )

  const groups = useMemo(() => {
    const pending = sorted.filter((t) => !isDone(t))
    const done = sorted.filter(isDone).sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1))
    if (filter === 'hechas') return [{ title: 'Completadas', items: done }]
    if (filter === 'todas') return [{ title: 'Pendientes', items: pending }, { title: 'Completadas', items: done }]
    const overdue = pending.filter((t) => t.due_date && daysUntil(t.due_date) < 0)
    const today = pending.filter((t) => t.due_date && daysUntil(t.due_date) === 0)
    if (filter === 'hoy') return [{ title: 'Vencidas', items: overdue, danger: true }, { title: 'Hoy', items: today }]
    const upcoming = pending.filter((t) => t.due_date && daysUntil(t.due_date) > 0)
    const nodate = pending.filter((t) => !t.due_date)
    return [
      { title: 'Vencidas', items: overdue, danger: true },
      { title: 'Hoy', items: today },
      { title: 'Próximas', items: upcoming },
      { title: 'Sin fecha', items: nodate },
    ]
  }, [sorted, filter])

  const pendingCount = items.filter((t) => !isDone(t)).length
  const doneCount = items.length - pendingCount

  const quickAdd = async (e) => {
    e.preventDefault()
    const title = text.trim()
    if (!title) return
    setText('')
    // Captura inteligente: "entregar práctica el viernes !alta", "sacar la basura cada lunes a las 21"...
    const item = buildCaptureItem(parseQuick(title), module, title)
    if (!item.due_date) item.due_date = quickDate || (filter === 'hoy' ? todayISO() : null)
    await create({ ...item, status: 'pendiente' })
  }

  const toggle = (t) => update(t.id, { status: isDone(t) ? 'pendiente' : 'hecha' })

  const clearDone = async () => {
    const done = items.filter(isDone)
    if (!done.length) return
    if (await confirm(`Se eliminarán ${done.length} tareas completadas.`)) {
      for (const t of done) await remove(t.id)
      toast('Tareas completadas eliminadas')
    }
  }

  const save = async (payload) => {
    if (editing === 'new') await create(payload)
    else await update(editing.id, payload)
  }

  return (
    <div className="page">
      <ModuleHeader
        module={module}
        subtitle={`${pendingCount} pendiente${pendingCount === 1 ? '' : 's'} · ${doneCount} completada${doneCount === 1 ? '' : 's'}`}
        actions={
          <button className="btn primary" onClick={() => setEditing('new')}>
            <Plus size={18} /> <span className="hide-sm">Nueva tarea</span>
          </button>
        }
      />

      <form className="quick-add" onSubmit={quickAdd}>
        <Plus size={18} className="muted" />
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Añadir tarea… «entregar práctica el viernes !alta», «regar plantas cada lunes»"
          aria-label="Nueva tarea"
        />
        <input type="date" value={quickDate} onChange={(e) => setQuickDate(e.target.value)} aria-label="Fecha" className="quick-date" />
        <button className="btn primary sm" disabled={!text.trim()}>
          Añadir
        </button>
        {text.trim() && parsed.understood && <SmartHint parsed={parsed} />}
      </form>

      <div className="toolbar">
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'hoy', label: 'Hoy' },
            { value: 'pendientes', label: 'Pendientes' },
            { value: 'hechas', label: 'Hechas' },
            { value: 'todas', label: 'Todas' },
          ]}
        />
        <span className="spacer" />
        {doneCount > 0 && (
          <button className="btn ghost sm" onClick={clearDone}>
            <Trash2 size={15} /> <span className="hide-sm">Limpiar completadas</span>
          </button>
        )}
      </div>

      {loading ? (
        <Spinner label="Cargando tareas…" />
      ) : !items.length ? (
        <EmptyState icon={CheckSquare} title="Sin tareas" text="Escribe arriba tu primera tarea y pulsa Enter." />
      ) : groups.every((g) => !g.items.length) ? (
        <EmptyState icon={CheckSquare} title="¡Todo al día!" text="No hay tareas en esta vista." />
      ) : (
        groups
          .filter((g) => g.items.length)
          .map((g) => (
            <section key={g.title} className="task-group">
              <h4 className={cx('group-title', g.danger && 'danger-text')}>
                {g.title} <span className="count">{g.items.length}</span>
              </h4>
              <div className="list">
                {g.items.map((t) => (
                  <TaskRow key={t.id} task={t} onToggle={() => toggle(t)} onOpen={() => setEditing(t)} />
                ))}
              </div>
            </section>
          ))
      )}

      {editing && (
        <ItemEditor
          module={module}
          item={editing === 'new' ? null : editing}
          onSave={save}
          onDelete={
            editing !== 'new'
              ? async () => {
                  if (await confirm(`Se eliminará la tarea "${editing.title}".`)) {
                    await remove(editing.id)
                    setEditing(null)
                  }
                }
              : undefined
          }
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function TaskRow({ task, onToggle, onOpen }) {
  const done = task.status === 'hecha'
  const n = task.due_date ? daysUntil(task.due_date) : null
  const p = task.data?.priority
  return (
    <div className={cx('row task-row', done && 'done')} onClick={onOpen}>
      <button
        className={cx('check', done && 'checked')}
        onClick={(e) => {
          e.stopPropagation()
          onToggle()
        }}
        aria-label={done ? 'Marcar como pendiente' : 'Marcar como hecha'}
        style={{ '--check': PRIORITY_COLOR[p] || 'var(--border-strong)' }}
      />
      <div className="row-main">
        <div className="row-title">{task.title}</div>
        <div className="item-meta">
          {task.due_date && (
            <span className={cx('meta due', !done && n < 0 && 'overdue', !done && n === 0 && 'soon')}>
              <Calendar size={12} /> {relativeDay(task.due_date)}
            </span>
          )}
          {task.data?.repeat && REPEAT_LABELS[task.data.repeat] && (
            <span className="meta" title="Se repite">
              <Repeat size={12} /> {REPEAT_LABELS[task.data.repeat]}
            </span>
          )}
          {p && p !== 'media' && (
            <span className="meta" style={{ color: PRIORITY_COLOR[p] }}>
              <Flag size={12} /> {p}
            </span>
          )}
          {task.body && <span className="meta ellipsis">{task.body}</span>}
          <Tags tags={task.tags} />
        </div>
      </div>
    </div>
  )
}
