import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import Modal from './Modal'
import { ICONS, COLORS } from '../lib/icons'
import { cx, slugify } from '../lib/utils'
import { CORE_KEYS } from '../lib/items'

const FIELD_TYPES = [
  { value: 'text', label: 'Texto corto' },
  { value: 'textarea', label: 'Texto largo' },
  { value: 'number', label: 'Número' },
  { value: 'money', label: 'Dinero (€)' },
  { value: 'date', label: 'Fecha' },
  { value: 'time', label: 'Hora' },
  { value: 'select', label: 'Lista de opciones' },
  { value: 'rating', label: 'Puntuación (estrellas)' },
  { value: 'progress', label: 'Progreso (%)' },
  { value: 'url', label: 'Enlace' },
  { value: 'checkbox', label: 'Sí / No' },
]

const EMPTY = {
  name: '',
  itemName: '',
  description: '',
  icon: 'Puzzle',
  color: '#7c5cff',
  layout: 'cards',
  titleLabel: 'Título',
  statuses: [
    { value: 'pendiente', label: 'Pendiente', color: '#64748b' },
    { value: 'en-curso', label: 'En curso', color: '#3b82f6' },
    { value: 'hecho', label: 'Hecho', color: '#22c55e' },
  ],
  fields: [],
  withDate: false,
  dateLabel: 'Fecha',
}

// Constructor visual de módulos: crea módulos nuevos sin escribir código.
export default function ModuleBuilder({ initial, existingIds, onSave, onClose }) {
  const [def, setDef] = useState(() => (initial ? structuredClone(initial) : structuredClone(EMPTY)))
  const [error, setError] = useState('')
  const set = (patch) => setDef((d) => ({ ...d, ...patch }))

  const setStatus = (i, patch) => set({ statuses: def.statuses.map((s, j) => (i === j ? { ...s, ...patch } : s)) })
  const setField = (i, patch) => set({ fields: def.fields.map((f, j) => (i === j ? { ...f, ...patch } : f)) })

  const submit = (e) => {
    e.preventDefault()
    if (!def.name.trim()) return setError('Ponle un nombre al módulo')
    let id = def.id
    if (!id) {
      id = `c-${slugify(def.name) || 'modulo'}`
      let n = 2
      while (existingIds.includes(id)) id = `c-${slugify(def.name)}-${n++}`
    }
    const usedKeys = new Set(CORE_KEYS)
    const fields = def.fields
      .filter((f) => f.label.trim())
      .map((f) => {
        let key = f.key || slugify(f.label).replace(/-/g, '_') || 'campo'
        while (usedKeys.has(key)) key += '_'
        usedKeys.add(key)
        const out = { key, label: f.label.trim(), type: f.type }
        if (f.type === 'select') {
          out.options = (f.optionsText || '')
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
            .map((label) => ({ value: slugify(label) || label, label }))
          out.optionsText = f.optionsText
        }
        return out
      })
    const statuses = def.statuses
      .filter((s) => s.label.trim())
      .map((s) => ({ ...s, value: s.value || slugify(s.label) || s.label }))
    onSave({ ...def, id, name: def.name.trim(), fields, statuses })
    onClose()
  }

  const Preview = ICONS[def.icon] || ICONS.Puzzle

  return (
    <Modal title={initial ? 'Editar módulo' : 'Crear módulo'} onClose={onClose} size="lg">
      <form className="form builder" onSubmit={submit}>
        <div className="builder-preview" style={{ '--mod': def.color }}>
          <span className="module-icon">
            <Preview size={24} />
          </span>
          <div>
            <strong>{def.name || 'Mi módulo'}</strong>
            <p className="muted small">{def.description || 'Descripción del módulo'}</p>
          </div>
        </div>

        <div className="grid-2">
          <div className="field">
            <label>Nombre del módulo *</label>
            <input autoFocus value={def.name} onChange={(e) => set({ name: e.target.value })} placeholder="Ej. Libros" />
          </div>
          <div className="field">
            <label>Cada elemento es un/a…</label>
            <input value={def.itemName} onChange={(e) => set({ itemName: e.target.value })} placeholder="Ej. libro" />
          </div>
        </div>
        <div className="field">
          <label>Descripción</label>
          <input value={def.description} onChange={(e) => set({ description: e.target.value })} placeholder="¿Para qué sirve?" />
        </div>

        <div className="field">
          <label>Icono</label>
          <div className="icon-picker">
            {Object.entries(ICONS).map(([name, Icon]) => (
              <button type="button" key={name} className={cx(def.icon === name && 'active')} onClick={() => set({ icon: name })} title={name}>
                <Icon size={18} />
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Color</label>
          <div className="color-picker">
            {COLORS.map((c) => (
              <button type="button" key={c} style={{ background: c }} className={cx(def.color === c && 'active')} onClick={() => set({ color: c })} aria-label={c} />
            ))}
          </div>
        </div>

        <div className="grid-2">
          <div className="field">
            <label>Vista por defecto</label>
            <select value={def.layout} onChange={(e) => set({ layout: e.target.value })}>
              <option value="cards">Tarjetas</option>
              <option value="list">Lista</option>
              <option value="board">Tablero (kanban)</option>
            </select>
          </div>
          <div className="field">
            <label>Nombre del campo principal</label>
            <input value={def.titleLabel} onChange={(e) => set({ titleLabel: e.target.value })} placeholder="Título" />
          </div>
        </div>

        <fieldset>
          <legend>Estados</legend>
          <p className="muted small">Déjalo vacío si el módulo no necesita estados.</p>
          {def.statuses.map((s, i) => (
            <div key={i} className="builder-row">
              <input type="color" value={s.color || '#64748b'} onChange={(e) => setStatus(i, { color: e.target.value })} aria-label="Color" />
              <input value={s.label} onChange={(e) => setStatus(i, { label: e.target.value })} placeholder="Nombre del estado" />
              <button type="button" className="icon-btn sm danger-text" onClick={() => set({ statuses: def.statuses.filter((_, j) => j !== i) })}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
          <button type="button" className="btn ghost xs" onClick={() => set({ statuses: [...def.statuses, { label: '', color: '#64748b' }] })}>
            <Plus size={13} /> Añadir estado
          </button>
        </fieldset>

        <fieldset>
          <legend>Campos extra</legend>
          <p className="muted small">Ya incluye título, etiquetas y notas. Añade lo que necesites: autor, precio, valoración…</p>
          {def.fields.map((f, i) => (
            <div key={i} className="builder-field">
              <div className="builder-row">
                <input value={f.label} onChange={(e) => setField(i, { label: e.target.value })} placeholder="Nombre del campo" />
                <select value={f.type} onChange={(e) => setField(i, { type: e.target.value })}>
                  {FIELD_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <button type="button" className="icon-btn sm danger-text" onClick={() => set({ fields: def.fields.filter((_, j) => j !== i) })}>
                  <Trash2 size={15} />
                </button>
              </div>
              {f.type === 'select' && (
                <input
                  className="builder-options"
                  value={f.optionsText ?? (f.options || []).map((o) => o.label).join(', ')}
                  onChange={(e) => setField(i, { optionsText: e.target.value })}
                  placeholder="Opciones separadas por comas: Tapa dura, Ebook, Audiolibro"
                />
              )}
            </div>
          ))}
          <button type="button" className="btn ghost xs" onClick={() => set({ fields: [...def.fields, { label: '', type: 'text' }] })}>
            <Plus size={13} /> Añadir campo
          </button>
        </fieldset>

        <div className="field inline">
          <label className="switch">
            <input type="checkbox" checked={def.withDate} onChange={(e) => set({ withDate: e.target.checked })} />
            <span />
          </label>
          <span>Tiene fecha (aparecerá en el calendario)</span>
          {def.withDate && <input value={def.dateLabel} onChange={(e) => set({ dateLabel: e.target.value })} placeholder="Nombre de la fecha" />}
        </div>

        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn primary">{initial ? 'Guardar cambios' : 'Crear módulo'}</button>
        </div>
      </form>
    </Modal>
  )
}
