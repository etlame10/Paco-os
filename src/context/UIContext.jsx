import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { CheckCircle2, AlertTriangle, Info, X } from 'lucide-react'
import Modal from '../components/Modal'

const UIContext = createContext(null)

// Notificaciones (toasts) y diálogos de confirmación accesibles desde cualquier módulo.
export function UIProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [confirmState, setConfirmState] = useState(null)
  const idRef = useRef(0)

  const toast = useCallback((message, type = 'success') => {
    const id = ++idRef.current
    setToasts((t) => [...t.slice(-2), { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500)
  }, [])

  const notifyError = useCallback(
    (e) => {
      console.error(e)
      toast(e?.message || 'Ha ocurrido un error', 'error')
    },
    [toast],
  )

  const confirm = useCallback(
    (message, { title = '¿Seguro?', confirmText = 'Eliminar', danger = true } = {}) =>
      new Promise((resolve) => setConfirmState({ message, title, confirmText, danger, resolve })),
    [],
  )

  const closeConfirm = (value) => {
    confirmState?.resolve(value)
    setConfirmState(null)
  }

  const icons = { success: CheckCircle2, error: AlertTriangle, info: Info }

  return (
    <UIContext.Provider value={{ toast, notifyError, confirm }}>
      {children}
      <div className="toasts" role="status">
        {toasts.map((t) => {
          const Icon = icons[t.type] || Info
          return (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <Icon size={18} />
              <span>{t.message}</span>
              <button className="icon-btn sm" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
      {confirmState && (
        <Modal title={confirmState.title} onClose={() => closeConfirm(false)} size="sm">
          <p className="muted">{confirmState.message}</p>
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => closeConfirm(false)}>
              Cancelar
            </button>
            <button
              className={`btn ${confirmState.danger ? 'danger' : 'primary'}`}
              autoFocus
              onClick={() => closeConfirm(true)}
            >
              {confirmState.confirmText}
            </button>
          </div>
        </Modal>
      )}
    </UIContext.Provider>
  )
}

export const useUI = () => useContext(UIContext)
