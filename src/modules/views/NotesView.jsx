import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, Search, Pin, Trash2, ChevronLeft, StickyNote, Check } from 'lucide-react'
import ModuleHeader from '../../components/ModuleHeader'
import FieldInput from '../../components/FieldInput'
import { EmptyState, Spinner } from '../../components/ui'
import { useItems } from '../../hooks/useItems'
import { useUI } from '../../context/UIContext'
import { cx, timeAgo } from '../../lib/utils'

// Notas con lista + editor y guardado automático.
export default function NotesView({ module }) {
  const { items, loading, create, update, remove } = useItems(module.id, { orderBy: 'updated_at' })
  const { confirm } = useUI()
  const [params, setParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    const id = params.get('item')
    if (id) {
      setSelectedId(id)
      params.delete('item')
      setParams(params, { replace: true })
    }
  }, [params, setParams])

  const notes = useMemo(() => {
    const q = query.toLowerCase().trim()
    const list = items
      .filter((n) => !q || n.title.toLowerCase().includes(q) || n.body.toLowerCase().includes(q) || n.tags?.some((t) => t.includes(q)))
      .sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1))
    return [...list.filter((n) => n.pinned), ...list.filter((n) => !n.pinned)]
  }, [items, query])

  const selected = items.find((n) => n.id === selectedId)

  const newNote = async () => {
    const row = await create({ title: '', body: '' })
    setSelectedId(row.id)
  }

  useEffect(() => {
    if (params.get('new') === '1') {
      params.delete('new')
      setParams(params, { replace: true })
      newNote()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  const del = async (note) => {
    if (await confirm(`Se eliminará la nota "${note.title || 'Sin título'}".`)) {
      await remove(note.id)
      setSelectedId(null)
    }
  }

  return (
    <div className={cx('page notes-page', selected && 'has-selection')}>
      <ModuleHeader
        module={module}
        subtitle={`${items.length} nota${items.length === 1 ? '' : 's'}`}
        actions={
          <button className="btn primary" onClick={newNote}>
            <Plus size={18} /> <span className="hide-sm">Nueva nota</span>
          </button>
        }
      />
      {loading ? (
        <Spinner label="Cargando notas…" />
      ) : !items.length ? (
        <EmptyState
          icon={StickyNote}
          title="Tu libreta está vacía"
          text="Crea tu primera nota. Se guarda sola mientras escribes."
          action={
            <button className="btn primary" onClick={newNote}>
              <Plus size={18} /> Nueva nota
            </button>
          }
        />
      ) : (
        <div className="notes-layout">
          <aside className="notes-list">
            <div className="search-box">
              <Search size={16} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar notas…" />
            </div>
            {notes.map((n) => (
              <button key={n.id} className={cx('note-item', n.id === selectedId && 'active')} onClick={() => setSelectedId(n.id)}>
                <div className="note-item-title">
                  {n.pinned && <Pin size={12} />}
                  {n.title || 'Sin título'}
                </div>
                <div className="note-item-body">{n.body.slice(0, 90) || 'Nota vacía'}</div>
                <div className="note-item-date">{timeAgo(n.updated_at)}</div>
              </button>
            ))}
          </aside>
          <section className="note-editor">
            {selected ? (
              <NoteEditor key={selected.id} note={selected} onChange={(p) => update(selected.id, p)} onDelete={() => del(selected)} onBack={() => setSelectedId(null)} />
            ) : (
              <EmptyState icon={StickyNote} title="Selecciona una nota" text="O crea una nueva con el botón de arriba." />
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function NoteEditor({ note, onChange, onDelete, onBack }) {
  const [title, setTitle] = useState(note.title)
  const [body, setBody] = useState(note.body)
  const [tags, setTags] = useState(note.tags || [])
  const [saved, setSaved] = useState(true)
  const timer = useRef(null)
  const pending = useRef(null)

  const schedule = (patch) => {
    setSaved(false)
    pending.current = { ...pending.current, ...patch }
    clearTimeout(timer.current)
    timer.current = setTimeout(flush, 700)
  }
  const flush = async () => {
    if (!pending.current) return
    const p = pending.current
    pending.current = null
    try {
      await onChange(p)
      setSaved(true)
    } catch {
      /* el error ya se notifica */
    }
  }
  // Guardar lo pendiente al cambiar de nota o salir.
  useEffect(() => () => {
    clearTimeout(timer.current)
    if (pending.current) onChange(pending.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="note-editor-inner">
      <div className="note-toolbar">
        <button className="icon-btn show-sm" onClick={onBack} aria-label="Volver">
          <ChevronLeft size={18} />
        </button>
        <span className="muted small">
          {saved ? (
            <>
              <Check size={12} /> Guardado
            </>
          ) : (
            'Guardando…'
          )}
        </span>
        <span className="spacer" />
        <button className={cx('icon-btn', note.pinned && 'active')} onClick={() => onChange({ pinned: !note.pinned })} title="Fijar en el inicio">
          <Pin size={17} />
        </button>
        <button className="icon-btn danger-text" onClick={onDelete} title="Eliminar">
          <Trash2 size={17} />
        </button>
      </div>
      <input
        className="note-title"
        value={title}
        placeholder="Título"
        autoFocus={!note.title}
        onChange={(e) => {
          setTitle(e.target.value)
          schedule({ title: e.target.value })
        }}
      />
      <FieldInput
        field={{ key: 'tags', type: 'tags', placeholder: '+ Añadir etiquetas' }}
        value={tags}
        onChange={(v) => {
          setTags(v)
          schedule({ tags: v })
        }}
      />
      <textarea
        className="note-body"
        value={body}
        placeholder="Empieza a escribir…"
        onChange={(e) => {
          setBody(e.target.value)
          schedule({ body: e.target.value })
        }}
      />
    </div>
  )
}
