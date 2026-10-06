import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Plus, Search, LayoutGrid, List, Columns3, Pin, ExternalLink, Calendar, ArrowUpDown,
} from 'lucide-react'
import ModuleHeader, { SummaryChips } from '../../components/ModuleHeader'
import ItemEditor from '../../components/ItemEditor'
import FieldValue, { hasValue } from '../../components/FieldValue'
import { Badge, EmptyState, Segmented, Spinner, Tags } from '../../components/ui'
import { useItems } from '../../hooks/useItems'
import { useUI } from '../../context/UIContext'
import { getField, statusOption } from '../../lib/items'
import { cx, daysUntil, relativeDay } from '../../lib/utils'

const SKIP_META = ['title', 'body', 'status', 'tags', 'due_date']

function usePersisted(key, initial) {
  const [v, setV] = useState(() => localStorage.getItem(key) || initial)
  useEffect(() => localStorage.setItem(key, v), [key, v])
  return [v, setV]
}

// Vista genérica para cualquier módulo de tipo "colección".
// Lista, tarjetas o tablero kanban, con búsqueda, filtros y orden.
export default function CollectionView({ module }) {
  const { items, loading, create, update, remove } = useItems(module.id)
  const { confirm, toast } = useUI()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [layout, setLayout] = usePersisted(`pacoos.layout.${module.id}`, module.layout || 'cards')
  const [sort, setSort] = usePersisted(`pacoos.sort.${module.id}`, module.sortDefault || 'recent')
  const [editing, setEditing] = useState(null) // null | 'new' | item | {new: true, initial}

  const statusField = module.fields.find((f) => f.key === 'status')
  const hasDate = module.fields.some((f) => f.key === 'due_date')
  const hasRating = module.fields.find((f) => f.type === 'rating')

  // Abrir un elemento concreto si viene en la URL (?item=id), p.ej. desde la búsqueda.
  useEffect(() => {
    const id = params.get('item')
    if (!id || loading) return
    const it = items.find((i) => i.id === id)
    if (it) setEditing(it)
    params.delete('item')
    setParams(params, { replace: true })
  }, [params, items, loading, setParams])

  useEffect(() => {
    if (params.get('new') === '1') {
      setEditing('new')
      params.delete('new')
      setParams(params, { replace: true })
    }
  }, [params, setParams])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let list = items.filter((i) => {
      if (statusFilter !== 'all' && i.status !== statusFilter) return false
      if (!q) return true
      return (
        i.title.toLowerCase().includes(q) ||
        (i.body || '').toLowerCase().includes(q) ||
        (i.tags || []).some((t) => t.toLowerCase().includes(q)) ||
        Object.values(i.data || {}).some((v) => String(v).toLowerCase().includes(q))
      )
    })
    const by = {
      recent: (a, b) => (b.updated_at > a.updated_at ? 1 : -1),
      title: (a, b) => a.title.localeCompare(b.title, 'es'),
      due_date: (a, b) => (a.due_date || '9999') .localeCompare(b.due_date || '9999'),
      rating: (a, b) => (Number(getField(b, hasRating?.key)) || 0) - (Number(getField(a, hasRating?.key)) || 0),
    }
    list = [...list].sort(by[sort] || by.recent)
    return [...list.filter((i) => i.pinned), ...list.filter((i) => !i.pinned)]
  }, [items, query, statusFilter, sort, hasRating])

  const save = async (payload) => {
    if (editing === 'new' || editing?.new) {
      await create(payload)
      toast(`Añadido a ${module.name}`)
    } else {
      await update(editing.id, payload)
      toast('Cambios guardados')
    }
  }

  const del = async (item) => {
    if (await confirm(`Se eliminará "${item.title || 'sin título'}" de forma permanente.`)) {
      await remove(item.id)
      setEditing(null)
      toast('Eliminado')
    }
  }

  const runAction = async (item, action) => {
    await update(item.id, action.run(item))
    toast(action.label)
  }

  const sortOptions = [
    { value: 'recent', label: 'Recientes' },
    { value: 'title', label: 'Nombre' },
    ...(hasDate ? [{ value: 'due_date', label: 'Fecha' }] : []),
    ...(hasRating ? [{ value: 'rating', label: 'Puntuación' }] : []),
  ]

  const cardProps = { module, onOpen: setEditing, onAction: runAction, onPin: (i) => update(i.id, { pinned: !i.pinned }) }

  return (
    <div className="page">
      <ModuleHeader
        module={module}
        actions={
          <button className="btn primary" onClick={() => setEditing('new')}>
            <Plus size={18} /> <span className="hide-sm">Añadir</span>
          </button>
        }
      />

      {module.summary && !loading && <SummaryChips stats={module.summary(items)} />}

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Buscar en ${module.name.toLowerCase()}…`} />
        </div>
        {statusField && layout !== 'board' && (
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="select-sm">
            <option value="all">Todos los estados</option>
            {statusField.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
        <label className="select-sm sort-select">
          <ArrowUpDown size={14} />
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <Segmented
          value={layout}
          onChange={setLayout}
          options={[
            { value: 'cards', icon: LayoutGrid, title: 'Tarjetas' },
            { value: 'list', icon: List, title: 'Lista' },
            ...(statusField ? [{ value: 'board', icon: Columns3, title: 'Tablero' }] : []),
          ]}
        />
      </div>

      {loading ? (
        <Spinner label="Cargando…" />
      ) : !items.length ? (
        <EmptyState
          icon={module.icon}
          title={`Aún no hay ${module.name.toLowerCase()}`}
          text={module.description}
          action={
            <button className="btn primary" onClick={() => setEditing('new')}>
              <Plus size={18} /> Añadir el primero
            </button>
          }
        />
      ) : layout === 'board' && statusField ? (
        <Board
          items={filtered}
          statusField={statusField}
          {...cardProps}
          onMove={(item, status) => item.status !== status && update(item.id, { status })}
          onAdd={(status) => setEditing({ new: true, initial: { status } })}
        />
      ) : !filtered.length ? (
        <EmptyState icon={Search} title="Sin resultados" text="Prueba con otra búsqueda o filtro." />
      ) : layout === 'list' ? (
        <div className="list">
          {filtered.map((i) => (
            <ItemRow key={i.id} item={i} {...cardProps} />
          ))}
        </div>
      ) : (
        <div className="cards">
          {filtered.map((i) => (
            <ItemCard key={i.id} item={i} {...cardProps} />
          ))}
        </div>
      )}

      {editing && (
        <ItemEditor
          module={module}
          item={editing === 'new' || editing.new ? null : editing}
          initial={editing.new ? editing.initial : undefined}
          onSave={save}
          onDelete={editing !== 'new' && !editing.new ? () => del(editing) : undefined}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function DueLabel({ date, module }) {
  if (!date) return null
  const n = daysUntil(date)
  const deadline = module.showInCalendar !== false
  return (
    <span className={cx('meta due', deadline && n < 0 && 'overdue', deadline && n >= 0 && n <= 2 && 'soon')}>
      <Calendar size={12} /> {relativeDay(date)}
    </span>
  )
}

function Actions({ module, item, onAction, onPin }) {
  const url = module.openUrlField && item.data?.[module.openUrlField]
  return (
    <div className="item-actions" onClick={(e) => e.stopPropagation()}>
      {(module.actions || [])
        .filter((a) => !a.when || a.when(item))
        .map((a) => (
          <button key={a.label} className={cx('btn xs', a.primary ? 'primary' : 'ghost')} onClick={() => onAction(item, a)} title={a.label}>
            {a.icon && <a.icon size={14} />} <span>{a.label}</span>
          </button>
        ))}
      {url && (
        <a className="icon-btn sm" href={url} target="_blank" rel="noreferrer" title="Abrir enlace">
          <ExternalLink size={15} />
        </a>
      )}
      <button className={cx('icon-btn sm', item.pinned && 'active')} onClick={() => onPin(item)} title={item.pinned ? 'Desfijar' : 'Fijar en inicio'}>
        <Pin size={15} />
      </button>
    </div>
  )
}

function metaFields(module, item) {
  return module.fields.filter(
    (f) => !SKIP_META.includes(f.key) && !f.hideInMeta && f.type !== 'textarea' && hasValue(getField(item, f.key)),
  )
}

function ItemCard({ item, module, onOpen, onAction, onPin }) {
  const status = statusOption(module, item.status)
  return (
    <article className={cx('card item-card', item.pinned && 'pinned')} onClick={() => onOpen(item)} style={{ '--mod': module.color }}>
      <div className="item-card-top">
        {status && <Badge color={status.color}>{status.label}</Badge>}
        <DueLabel date={item.due_date} module={module} />
      </div>
      <h3 className="item-title">{item.title || 'Sin título'}</h3>
      {module.subtitle?.(item) && <p className="item-sub">{module.subtitle(item)}</p>}
      <div className="item-meta">
        {metaFields(module, item).map((f) => (
          <FieldValue key={f.key} field={f} value={getField(item, f.key)} color={module.color} />
        ))}
      </div>
      {item.body && <p className="item-body">{item.body}</p>}
      <Tags tags={item.tags} />
      <Actions module={module} item={item} onAction={onAction} onPin={onPin} />
    </article>
  )
}

function ItemRow({ item, module, onOpen, onAction, onPin }) {
  const status = statusOption(module, item.status)
  return (
    <div className={cx('row item-row', item.pinned && 'pinned')} onClick={() => onOpen(item)}>
      <span className="row-dot" style={{ background: status?.color || module.color }} />
      <div className="row-main">
        <div className="row-title">
          {item.title || 'Sin título'}
          {module.subtitle?.(item) && <span className="item-sub inline">{module.subtitle(item)}</span>}
        </div>
        <div className="item-meta">
          {status && <Badge color={status.color}>{status.label}</Badge>}
          <DueLabel date={item.due_date} module={module} />
          {metaFields(module, item)
            .filter((f) => f.type !== 'progress')
            .slice(0, 4)
            .map((f) => (
              <FieldValue key={f.key} field={f} value={getField(item, f.key)} color={module.color} />
            ))}
          {(item.tags || []).slice(0, 3).map((t) => (
            <span key={t} className="tag">
              #{t}
            </span>
          ))}
        </div>
      </div>
      <Actions module={module} item={item} onAction={onAction} onPin={onPin} />
    </div>
  )
}

function Board({ items, statusField, module, onOpen, onAction, onPin, onMove, onAdd }) {
  const [over, setOver] = useState(null)
  return (
    <div className="board">
      {statusField.options.map((col) => {
        const colItems = items.filter((i) => (i.status || statusField.default) === col.value)
        return (
          <section
            key={col.value}
            className={cx('board-col', over === col.value && 'over')}
            onDragOver={(e) => {
              e.preventDefault()
              setOver(col.value)
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              setOver(null)
              const it = items.find((i) => i.id === e.dataTransfer.getData('text/plain'))
              if (it) onMove(it, col.value)
            }}
          >
            <header>
              <span className="row-dot" style={{ background: col.color }} />
              <strong>{col.label}</strong>
              <span className="count">{colItems.length}</span>
              <button className="icon-btn sm" onClick={() => onAdd(col.value)} title="Añadir aquí">
                <Plus size={15} />
              </button>
            </header>
            <div className="board-items">
              {colItems.map((i) => (
                <div key={i.id} draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', i.id)}>
                  <ItemCard item={i} module={module} onOpen={onOpen} onAction={onAction} onPin={onPin} />
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
