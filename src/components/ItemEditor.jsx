import { useState } from 'react'
import { Pin, PinOff, Trash2 } from 'lucide-react'
import Modal from './Modal'
import FieldInput from './FieldInput'
import { defaultForm, formToItem, itemToForm } from '../lib/items'

// Formulario genérico de crear/editar, generado a partir de los campos del módulo.
export default function ItemEditor({ module, item, initial, onSave, onDelete, onClose }) {
  const isNew = !item
  const [values, setValues] = useState(() =>
    isNew ? defaultForm(module.fields, initial) : itemToForm(item, module.fields),
  )
  const [pinned, setPinned] = useState(item?.pinned ?? false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (k, v) => setValues((prev) => ({ ...prev, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    const missing = module.fields.find((f) => f.required && (values[f.key] === '' || values[f.key] == null))
    if (missing) return setError(`El campo "${missing.label}" es obligatorio`)
    setSaving(true)
    try {
      const payload = formToItem(values, item?.data)
      payload.pinned = pinned
      await onSave(payload)
      onClose()
    } catch {
      setSaving(false)
    }
  }

  const title = isNew ? `Nuevo ${module.itemName || 'elemento'}` : `Editar ${module.itemName || 'elemento'}`

  return (
    <Modal title={title} onClose={onClose} size="md">
      <form onSubmit={submit} className="form">
        {module.fields.map((f, idx) => (
          <div key={f.key} className={`field field-${f.type}`}>
            <label htmlFor={`f-${f.key}`}>
              {f.label}
              {f.required && <span className="req">*</span>}
            </label>
            <FieldInput field={f} value={values[f.key]} onChange={(v) => set(f.key, v)} autoFocus={idx === 0 && isNew} />
          </div>
        ))}
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          {!isNew && onDelete && (
            <button type="button" className="btn ghost danger-text" onClick={onDelete}>
              <Trash2 size={16} /> Eliminar
            </button>
          )}
          <button type="button" className="btn ghost" onClick={() => setPinned(!pinned)} title="Fijar en el inicio">
            {pinned ? <PinOff size={16} /> : <Pin size={16} />} {pinned ? 'Desfijar' : 'Fijar'}
          </button>
          <span className="spacer" />
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn primary" disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
