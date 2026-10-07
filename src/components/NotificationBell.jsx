import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Bell, BellOff, Clock, Settings, X } from 'lucide-react'
import { api } from '../lib/api'
import { useSettings } from '../context/SettingsContext'
import { formatDateTime } from '../lib/notifications/time'
import { cx } from '../lib/utils'

const KIND_ICON = { task: '✅', exam: '🎓', event: '📅', custom: '🔔', system: '✨' }

// Campana con los avisos recientes (bandeja) y los próximos programados.
export default function NotificationBell({ className }) {
  const { notificationPrefs } = useSettings()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [recent, setRecent] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const btnRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const [r, u] = await Promise.all([api.notifications.listRecent(15), api.notifications.listUpcoming(10)])
      setRecent(r)
      setUpcoming(u)
    } catch {
      // Si las tablas aún no existen en Supabase, la campana simplemente queda vacía.
      setRecent([])
      setUpcoming([])
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 60000)
    const onVisible = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [load])

  const unread = recent.filter((n) => n.status === 'sent' && !n.read_at).length

  const toggle = async () => {
    const next = !open
    setOpen(next)
    if (next) {
      await load()
      if (unread) api.notifications.markAllRead().catch(() => undefined)
    } else if (unread) {
      setRecent((r) => r.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() })))
    }
  }

  const go = (n) => {
    setOpen(false)
    if (n.url) navigate(n.url.replace(/^#/, ''))
  }

  const tz = notificationPrefs.timezone

  return (
    <>
      <button ref={btnRef} className={cx('icon-btn bell', className)} onClick={toggle} aria-label="Avisos" title="Avisos">
        <Bell size={18} />
        {unread > 0 && <span className="bell-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open &&
        createPortal(
          <div className="bell-backdrop" onMouseDown={(e) => e.target === e.currentTarget && toggle()}>
            <div className="bell-panel" role="dialog" aria-label="Avisos">
              <header>
                <strong>Avisos</strong>
                <span className="spacer" />
                <button
                  className="icon-btn sm"
                  title="Ajustes de notificaciones"
                  onClick={() => {
                    setOpen(false)
                    navigate('/ajustes?seccion=notificaciones')
                  }}
                >
                  <Settings size={15} />
                </button>
                <button className="icon-btn sm" onClick={toggle} aria-label="Cerrar">
                  <X size={15} />
                </button>
              </header>
              <div className="bell-body">
                <h5>Recientes</h5>
                {recent.length ? (
                  recent.map((n) => (
                    <button key={n.id} className={cx('bell-item', !n.read_at && n.status === 'sent' && 'unread')} onClick={() => go(n)}>
                      <span className="bell-kind">{KIND_ICON[n.kind] || '🔔'}</span>
                      <span className="bell-text">
                        <strong>{n.title}</strong>
                        {n.body && <small>{n.body}</small>}
                      </span>
                      <small className="muted">{n.sent_at ? formatDateTime(n.sent_at, tz) : ''}</small>
                    </button>
                  ))
                ) : (
                  <p className="muted small bell-empty">
                    <BellOff size={14} /> Todavía no has recibido avisos.
                  </p>
                )}
                <h5>Próximos</h5>
                {upcoming.length ? (
                  upcoming.map((n) => (
                    <button key={n.id} className="bell-item" onClick={() => go(n)}>
                      <span className="bell-kind">{KIND_ICON[n.kind] || '🔔'}</span>
                      <span className="bell-text">
                        <strong>{n.title}</strong>
                        {n.body && <small>{n.body}</small>}
                      </span>
                      <small className="muted">
                        <Clock size={11} /> {formatDateTime(n.remind_at, tz)}
                      </small>
                    </button>
                  ))
                ) : (
                  <p className="muted small bell-empty">Nada programado. Pon fecha a tus tareas, exámenes o avisos.</p>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
