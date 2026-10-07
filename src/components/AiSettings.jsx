import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Segmented } from './ui'
import { useAuth } from '../context/AuthContext'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { api, isLocalMode } from '../lib/api'
import { PERMISSION_KINDS, PERMISSION_LABELS, getAiPermissions } from '../lib/ai/permissions'
import { clearChat as clearStoredChat } from '../lib/ai/storage'

// Ajustes → PACO AI: estado del servicio y qué puede hacer la IA sin preguntar.
export default function AiSettings() {
  const { user } = useAuth()
  const { settings, update } = useSettings()
  const { toast, confirm } = useUI()
  const [status, setStatus] = useState(null)
  const permissions = getAiPermissions(settings)

  useEffect(() => {
    let alive = true
    api.ai
      .status()
      .then((s) => alive && setStatus(s))
      .catch((e) => alive && setStatus({ error: e.message }))
    return () => {
      alive = false
    }
  }, [])

  const setPermission = (kind, value) =>
    update((prev) => ({ ai: { ...prev.ai, permissions: { ...getAiPermissions(prev), [kind]: value } } }))

  const clearChat = async () => {
    if (!(await confirm('Se borrará la conversación de PACO AI guardada en este dispositivo.', { title: 'Borrar conversación', confirmText: 'Borrar' }))) return
    clearStoredChat(user?.id)
    toast('Conversación borrada')
  }

  const ready = status && !status.error && status.configured && status.allowed

  return (
    <section className="card settings-section" id="paco-ai">
      <h3 className="section-title">
        <Sparkles size={16} /> PACO AI
      </h3>

      <div className={ready ? 'notice' : 'notice notice-danger'}>
        {ready ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
        <span>
          {!status
            ? 'Comprobando…'
            : isLocalMode || status.local
              ? 'PACO AI necesita Supabase (no funciona en modo local).'
              : status.error
                ? status.error
                : !status.configured
                  ? 'Falta configurar la Edge Function "paco-ai" (ver docs/PACO_AI.md).'
                  : !status.allowed
                    ? 'Tu cuenta no está en PACO_AI_ALLOWED_EMAILS.'
                    : `Activo · modelo ${status.model} · hoy ${status.requests_today}/${status.daily_limit} peticiones.`}
        </span>
      </div>

      <p className="muted small">
        Elige qué puede hacer la IA por su cuenta. Estas reglas se aplican en tu dispositivo antes de ejecutar cualquier acción, diga lo que diga la
        IA. Borrar siempre pide confirmación.
      </p>

      {PERMISSION_KINDS.map((p) => (
        <div key={p.kind} className="ai-perm-row">
          <div>
            <strong>{p.label}</strong>
            <div className="muted small">{p.hint}</div>
          </div>
          <Segmented
            value={permissions[p.kind]}
            onChange={(v) => setPermission(p.kind, v)}
            options={p.options.map((o) => ({ value: o, label: PERMISSION_LABELS[o] }))}
          />
        </div>
      ))}

      <p className="muted small">
        Privacidad: para responderte, lo que PACO AI consulta (elementos, fechas, nombres de archivos) se envía a Anthropic, el proveedor del modelo. El
        contenido de tus archivos nunca se envía. La conversación solo se guarda en este dispositivo.
      </p>
      <div className="btn-row">
        <Link to="/ai" className="btn ghost sm">
          <Sparkles size={15} /> Abrir PACO AI
        </Link>
        <button className="btn ghost sm" onClick={clearChat}>
          <Trash2 size={15} /> Borrar conversación de este dispositivo
        </button>
      </div>
    </section>
  )
}
