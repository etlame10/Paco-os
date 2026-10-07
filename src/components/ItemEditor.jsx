import { useState } from 'react'
import { Bell, Pin, PinOff, Trash2 } from 'lucide-react'
import Modal from './Modal'
import FieldInput from './FieldInput'
import { defaultForm, formToItem, itemToForm } from '../lib/items'
import { useSettings } from '../context/SettingsContext'
import { describeDefaultReminder, resolveNotificationConfig } from '../lib/notifications/rules'

function ReminderField({ value, onChange, hint, hasDate }) {
  const mode = value === 'default' || value === 'none' ? value : 'custom'
  return (
    <div className="field field-reminder">
      <label htmlFor="f-reminder">
        <Bell size={13} /> Recordatorio
      </label>
      <div className="reminder-row">
        <select
          id="f-reminder"
          value={mode}
          onChange={(e) => {
            const m = e.target.value
            onChange(m === 'custom' ? '' : m)
          }}
        >
          <option value="default">{hasDate ? `Por defecto (${hint})` : 'Por defecto (necesita fecha)'}</option>
          <option value="custom">Fecha y hora concretas…</option>
          <option value="none">Sin aviso</option>
        </select>
        {mode === 'custom' && (
          <input type="datetime-local" value={value || ''} onChange={(e) => onChange(e.target.value)} aria-label="Fecha y hora del aviso" />
        )}
      </div>
    </div>
  )
}

// Formulario genérico de crear/editar, generado a partir de los campos del módulo.
export default function ItemEditor({ module, item, initial, onSave, onDelete, onClose }) {
  const isNew = !item
  const [values, setValues] = useState(() =>
    isNew ? defaultForm(module.fields, initial) : itemToForm(item, module.fields),
  )
  const [pinned, setPinned] = useState(item?.pinned ?? false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Recordatorio (solo en módulos que admiten avisos): 'default' | 'none' | 'YYYY-MM-DDTHH:MM'
  const { notificationPrefs } = useSettings()
  const reminderEnabled = Boolean(resolveNotificationConfig(module))
  const [reminder, setReminder] = useState(item?.data?.reminder || 'default')

  const set = (k, v) => setValues((prev) => ({ ...prev, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    const missing = module.fields.find((f) => f.required && (values[f.key] === '' || values[f.key] == null))
    if (missing) return setError(`El campo "${missing.label}" es obligatorio`)
    if (reminderEnabled && reminder !== 'default' && reminder !== 'none' && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(reminder)) {
      return setError('Indica la fecha y la hora del recordatorio personalizado')
    }
    setSaving(true)
    try {
      const payload = formToItem(values, item?.data)
      if (reminderEnabled) {
        if (reminder === 'default') delete payload.data.reminder
        else payload.data.reminder = reminder
      }
      payload.pinned = pinned
      await onSave(payload)
      onClose()
    } catch {
      setSaving(false)
    }
  }

  const noun = module.itemName || 'elemento'
  const title = isNew ? `${/a$/.test(noun) ? 'Nueva' : 'Nuevo'} ${noun}` : `Editar ${noun}`

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
        {reminderEnabled && (
          <ReminderField
            value={reminder}
            onChange={setReminder}
            hint={describeDefaultReminder(module, notificationPrefs, { ...item, data: { ...item?.data, ...values } })}
            hasDate={Boolean(values.due_date)}
          />
        )}
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
