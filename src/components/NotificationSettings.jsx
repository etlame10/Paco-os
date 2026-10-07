import { useCallback, useEffect, useState } from 'react'
import { Bell, BellOff, Send, Smartphone, Trash2, Share, PlusSquare, Download, AlertTriangle } from 'lucide-react'
import { api, isLocalMode } from '../lib/api'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { useInstallPrompt } from '../hooks/useInstallPrompt'
import { NOTIFICATION_KINDS } from '../lib/notifications/prefs'
import { browserTimeZone } from '../lib/notifications/time'
import {
  disablePushOnThisDevice,
  enablePushOnThisDevice,
  getCurrentSubscription,
  isIOS,
  isPushConfigured,
  isPushSupported,
  isStandalone,
  permissionState,
} from '../lib/notifications/push'
import { timeAgo } from '../lib/utils'

const TIMEZONES = ['Europe/Madrid', 'Atlantic/Canary', 'Europe/London', 'Europe/Lisbon', 'America/Mexico_City', 'America/Bogota', 'America/Argentina/Buenos_Aires', 'UTC']

export default function NotificationSettings() {
  const { notificationPrefs: prefs, updateNotificationPrefs } = useSettings()
  const { toast, notifyError, confirm } = useUI()
  const { canInstall, install } = useInstallPrompt()
  const [devices, setDevices] = useState([])
  const [thisEndpoint, setThisEndpoint] = useState(null)
  const [busy, setBusy] = useState(false)
  const [permission, setPermission] = useState(permissionState())

  const ios = isIOS()
  const standalone = isStandalone()
  const supported = isPushSupported()

  const refresh = useCallback(async () => {
    setPermission(permissionState())
    try {
      const sub = await getCurrentSubscription()
      setThisEndpoint(sub?.endpoint || null)
    } catch {
      setThisEndpoint(null)
    }
    try {
      setDevices(await api.push.listSubscriptions())
    } catch {
      setDevices([])
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const thisDeviceActive = Boolean(thisEndpoint && devices.some((d) => d.endpoint === thisEndpoint))

  const enable = async () => {
    setBusy(true)
    try {
      await enablePushOnThisDevice()
      toast('Notificaciones activadas en este dispositivo')
    } catch (e) {
      notifyError(e)
    } finally {
      setBusy(false)
      refresh()
    }
  }

  const disable = async () => {
    setBusy(true)
    try {
      await disablePushOnThisDevice()
      toast('Notificaciones desactivadas en este dispositivo', 'info')
    } catch (e) {
      notifyError(e)
    } finally {
      setBusy(false)
      refresh()
    }
  }

  const test = async () => {
    setBusy(true)
    try {
      const r = await api.push.sendTest()
      toast(r?.sent ? `Aviso de prueba enviado a ${r.sent} dispositivo${r.sent > 1 ? 's' : ''}` : 'No hay dispositivos activos', r?.sent ? 'success' : 'info')
    } catch (e) {
      notifyError(e)
    } finally {
      setBusy(false)
      refresh()
    }
  }

  const removeDevice = async (d) => {
    if (!(await confirm(`Este dispositivo dejará de recibir avisos: ${d.device_name || 'dispositivo'}.`, { confirmText: 'Quitar' }))) return
    try {
      await api.push.removeSubscription(d.id)
      if (d.endpoint === thisEndpoint) await disablePushOnThisDevice().catch(() => undefined)
      refresh()
    } catch (e) {
      notifyError(e)
    }
  }

  const tzOptions = [...new Set([prefs.timezone, browserTimeZone(), ...TIMEZONES])]

  return (
    <section className="card settings-section" id="notificaciones">
      <h3 className="section-title">
        <Bell size={16} /> Notificaciones
      </h3>

      {/* ---- Estado de este dispositivo ---- */}
      {isLocalMode ? (
        <div className="notice">
          <AlertTriangle size={18} />
          <span>Modo local: los avisos solo se muestran mientras PACO OS está abierto. Las notificaciones push necesitan Supabase.</span>
        </div>
      ) : !isPushConfigured ? (
        <div className="notice">
          <AlertTriangle size={18} />
          <span>
            Las notificaciones push aún no están configuradas en esta web (falta <code>VITE_VAPID_PUBLIC_KEY</code>). Los avisos se
            siguen programando y aparecen en la campana. Ver <code>docs/NOTIFICACIONES.md</code>.
          </span>
        </div>
      ) : ios && !standalone ? (
        <div className="notice">
          <Smartphone size={18} />
          <span>
            En iPhone/iPad (iOS 16.4 o superior) primero instala PACO OS: en Safari pulsa <Share size={13} /> <strong>Compartir</strong> →{' '}
            <PlusSquare size={13} /> <strong>Añadir a pantalla de inicio</strong>, ábrelo desde el icono y vuelve aquí.
          </span>
        </div>
      ) : !supported ? (
        <div className="notice">
          <BellOff size={18} />
          <span>Este navegador no admite notificaciones push. Prueba con Chrome, Edge, Firefox o Safari actualizados.</span>
        </div>
      ) : permission === 'denied' ? (
        <div className="notice">
          <BellOff size={18} />
          <span>
            Has bloqueado las notificaciones de PACO OS. Actívalas desde los ajustes del navegador o del sistema (permisos del sitio) y
            recarga la página.
          </span>
        </div>
      ) : (
        <div className="btn-row">
          {thisDeviceActive ? (
            <>
              <span className="badge" style={{ '--badge': 'var(--ok)' }}>
                Activas en este dispositivo
              </span>
              <button className="btn ghost sm" onClick={test} disabled={busy}>
                <Send size={15} /> Enviar aviso de prueba
              </button>
              <button className="btn ghost sm" onClick={disable} disabled={busy}>
                <BellOff size={15} /> Desactivar aquí
              </button>
            </>
          ) : (
            <button className="btn primary" onClick={enable} disabled={busy}>
              <Bell size={16} /> Activar notificaciones en este dispositivo
            </button>
          )}
        </div>
      )}

      {canInstall && (
        <button className="btn ghost sm" onClick={install}>
          <Download size={15} /> Instalar PACO OS como app
        </button>
      )}

      {/* ---- Dispositivos ---- */}
      {!isLocalMode && devices.length > 0 && (
        <div className="field">
          <label>Dispositivos que reciben avisos</label>
          <div className="list compact">
            {devices.map((d) => (
              <div key={d.id} className="row">
                <Smartphone size={16} />
                <div className="row-main">
                  <span>
                    {d.device_name || 'Dispositivo'} {d.endpoint === thisEndpoint && <span className="badge">este</span>}
                  </span>
                  <small className="muted">
                    Último uso {timeAgo(d.last_seen_at || d.created_at)}
                    {d.failure_count > 0 ? ` · ${d.failure_count} fallos` : ''}
                  </small>
                </div>
                <button className="icon-btn sm danger-text" onClick={() => removeDevice(d)} title="Quitar dispositivo">
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---- Preferencias ---- */}
      <div className="field">
        <label>Qué quiero recibir</label>
        <div className="list compact">
          {NOTIFICATION_KINDS.map((k) => (
            <label key={k.id} className="row toggle-row">
              <div className="row-main">
                <span>{k.label}</span>
                <small className="muted">{k.description}</small>
              </div>
              <span className="switch">
                <input
                  type="checkbox"
                  checked={prefs.kinds[k.id] !== false}
                  onChange={(e) => updateNotificationPrefs({ kinds: { ...prefs.kinds, [k.id]: e.target.checked } })}
                />
                <span />
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid-2">
        <div className="field">
          <label htmlFor="n-task">Tareas: hora del aviso (día límite)</label>
          <input id="n-task" type="time" value={prefs.taskTime} onChange={(e) => e.target.value && updateNotificationPrefs({ taskTime: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="n-event">Eventos: hora del aviso (mismo día)</label>
          <input id="n-event" type="time" value={prefs.eventTime} onChange={(e) => e.target.value && updateNotificationPrefs({ eventTime: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="n-exam">Exámenes: hora del aviso</label>
          <input id="n-exam" type="time" value={prefs.examTime} onChange={(e) => e.target.value && updateNotificationPrefs({ examTime: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="n-exam-days">Exámenes: días de antelación</label>
          <select id="n-exam-days" value={prefs.examDaysBefore} onChange={(e) => updateNotificationPrefs({ examDaysBefore: Number(e.target.value) })}>
            {[0, 1, 2, 3, 7].map((d) => (
              <option key={d} value={d}>
                {d === 0 ? 'El mismo día' : d === 1 ? '1 día antes' : `${d} días antes`}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Horas de silencio</label>
          <div className="reminder-row">
            <input type="time" value={prefs.quietStart} onChange={(e) => updateNotificationPrefs({ quietStart: e.target.value })} aria-label="Inicio" />
            <span className="muted">a</span>
            <input type="time" value={prefs.quietEnd} onChange={(e) => updateNotificationPrefs({ quietEnd: e.target.value })} aria-label="Fin" />
          </div>
          <small className="muted">Los avisos que caigan en esta franja se entregan al terminar.</small>
        </div>
        <div className="field">
          <label htmlFor="n-tz">Zona horaria</label>
          <select id="n-tz" value={prefs.timezone} onChange={(e) => updateNotificationPrefs({ timezone: e.target.value })}>
            {tzOptions.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="muted small">
        Cada tarea, examen o aviso puede tener su propio recordatorio (o ninguno) desde su formulario. Si cambias estas horas, los avisos
        futuros se recalculan solos.
      </p>
    </section>
  )
}
