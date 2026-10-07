import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, Send, Square, Plus, ShieldCheck, Check, X, AlertTriangle, Loader2, Search, PenLine, Trash2, FilePlus2, RotateCcw, Ban, Paperclip, FileText } from 'lucide-react'
import ModuleHeader from '../components/ModuleHeader'
import Markdown from '../components/Markdown'
import DocumentPicker from '../components/DocumentPicker'
import { useAuth } from '../context/AuthContext'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { api, isLocalMode } from '../lib/api'
import { supabaseEnvProblem } from '../lib/supabase'
import { createToolbox, modulesSummary } from '../lib/ai/tools'
import { getAiPermissions } from '../lib/ai/permissions'
import { attachmentNames, buildUserMessage, pendingToolUses, runAgent } from '../lib/ai/agent'
import { emitItemsChanged } from '../lib/runtimeContext'
import { loadChat, saveChat } from '../lib/ai/storage'
import { cx } from '../lib/utils'

const MAX_LOCAL_CHARS = 1_000_000

const SUGGESTIONS = [
  '¿Qué tengo esta semana?',
  'Crea una tarea para mañana: llamar al banco',
  'Recuérdame el viernes a las 18:00 ir al gimnasio',
  '¿Qué tareas tengo pendientes con prioridad alta?',
]

const TOOL_LABELS = {
  list_modules: 'Consultar módulos',
  search_items: 'Buscar elementos',
  get_item: 'Leer elemento',
  read_document: 'Leer documento',
  get_agenda: 'Consultar agenda',
  list_files: 'Consultar archivos',
  create_item: 'Crear elemento',
  update_item: 'Editar elemento',
  delete_item: 'Eliminar elemento',
}

const KIND_ICONS = { read: Search, document: FileText, create: FilePlus2, update: PenLine, delete: Trash2 }

const STATUS_TEXT = {
  done: 'Hecho',
  pending: 'Esperando tu confirmación',
  rejected: 'Rechazado',
  blocked: 'No permitido',
  error: 'Error',
}

const visibleUserText = (msg) =>
  typeof msg.content === 'string'
    ? msg.content
    : msg.content
        .filter((b) => b.type === 'text' && !b.text.startsWith('<')) // contexto y adjuntos: no se muestran como texto
        .map((b) => b.text)
        .join('\n')

export default function Assistant() {
  const { user } = useAuth()
  const { settings, enabledModules, getModule, notificationPrefs } = useSettings()
  const { confirm } = useUI()
  const [chat, setChat] = useState(() => loadChat(user?.id))
  const [status, setStatus] = useState(null)
  const [usage, setUsage] = useState(null)
  const [running, setRunning] = useState(false)
  const [approval, setApproval] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const stopRef = useRef(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => saveChat(user?.id, chat), [user?.id, chat])

  useEffect(() => {
    let alive = true
    api.ai
      .status()
      .then((s) => {
        if (!alive) return
        setStatus(s)
        if (s?.daily_limit) setUsage({ requests_today: s.requests_today, daily_limit: s.daily_limit })
      })
      .catch((e) => alive && setStatus({ error: e.message }))
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.messages.length, approval, running])

  const permissions = useMemo(() => getAiPermissions(settings), [settings])
  const pending = pendingToolUses(chat.messages)
  const last = chat.messages[chat.messages.length - 1]
  const canResume = !running && (pending.length > 0 || last?.role === 'user')
  const ready = !isLocalMode && status && !status.error && status.configured && status.allowed

  const run = useCallback(
    // interaction: identificador del mensaje del usuario que se está atendiendo. Todas las
    // llamadas internas (herramientas, «Reintentar», «Continuar») lo comparten: 1 uso.
    async (messages, newKeys = [], interaction = chat.interaction || crypto.randomUUID()) => {
      setChat((c) => (c.interaction === interaction ? c : { ...c, interaction }))
      const context = { modules: modulesSummary(enabledModules) }
      setRunning(true)
      setError(null)
      setNotice(null)
      stopRef.current = false
      const toolbox = createToolbox({ api, modules: enabledModules, getModule })
      try {
        const result = await runAgent({
          messages,
          toolbox,
          permissions,
          interactionId: interaction,
          send: async (msgs, { interactionId }) => {
            const r = await api.ai.chat(msgs, { interactionId, context })
            if (r?.usage) setUsage(r.usage)
            return r
          },
          approve: (actions) => new Promise((resolve) => setApproval({ actions, decisions: {}, resolve })),
          onMessages: (m) => setChat((c) => ({ ...c, messages: m })),
          onAction: (id, info) => {
            setChat((c) => ({ ...c, actions: { ...c.actions, [id]: info } }))
            if (info.status === 'done' && info.kind !== 'read') emitItemsChanged({ type: 'ai', module: info.module })
          },
          isStopped: () => stopRef.current,
          // Documentos ya autorizados en esta conversación (adjuntados o aprobados antes).
          approvedKeys: new Set([...(chat.approved || []), ...newKeys]),
          onRemember: (key) => setChat((c) => ({ ...c, approved: [...new Set([...(c.approved || []), key])] })),
        })
        if (result.status === 'refusal') setNotice('PACO AI no ha podido responder a esa petición.')
        if (result.status === 'max_tokens') setNotice('La respuesta era demasiado larga y se ha cortado. Prueba a pedirlo por partes.')
        if (result.status === 'limit') setNotice('PACO AI se ha detenido tras demasiados pasos seguidos. Pulsa «Continuar» si quieres que siga.')
        if (result.status === 'stopped') setNotice('Conversación detenida.')
      } catch (e) {
        setError(e)
      } finally {
        setRunning(false)
        setApproval(null)
      }
    },
    [enabledModules, getModule, permissions, chat.approved, chat.interaction],
  )

  const submit = (text) => {
    const t = (text ?? input).trim()
    if (!t || running || pending.length) return
    const msg = buildUserMessage(t, { timezone: notificationPrefs.timezone, userName: settings.displayName, attachments })
    const next = [...chat.messages, msg]
    const keys = attachments.map((f) => `file:${f.id}`)
    if (JSON.stringify(next).length > MAX_LOCAL_CHARS) {
      setError({ message: 'La conversación es demasiado larga. Empieza una nueva con «Nueva conversación».', code: 'conversation_too_long' })
      return
    }
    const interaction = crypto.randomUUID() // un mensaje nuevo = una interacción nueva
    setChat((c) => ({ ...c, messages: next, interaction, approved: [...new Set([...(c.approved || []), ...keys])] }))
    setInput('')
    setAttachments([])
    run(next, keys, interaction)
  }

  const stop = () => {
    stopRef.current = true
    if (approval) {
      approval.resolve(new Set())
      setApproval(null)
    }
  }

  const decide = (id, ok) => {
    setApproval((a) => {
      if (!a) return a
      const decisions = { ...a.decisions, [id]: ok }
      if (a.actions.every((x) => x.id in decisions)) {
        a.resolve(new Set(a.actions.filter((x) => decisions[x.id]).map((x) => x.id)))
        return null
      }
      return { ...a, decisions }
    })
  }

  const decideAll = (ok) => {
    setApproval((a) => {
      if (!a) return a
      a.resolve(new Set(ok ? a.actions.map((x) => x.id) : []))
      return null
    })
  }

  const newChat = async () => {
    if (running) return
    if (chat.messages.length && !(await confirm('Se borrará la conversación actual de este dispositivo.', { title: 'Nueva conversación', confirmText: 'Empezar de nuevo' })))
      return
    setChat({ messages: [], actions: {}, approved: [], interaction: null })
    setAttachments([])
    setError(null)
    setNotice(null)
    inputRef.current?.focus()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const resultsById = useMemo(() => {
    const ids = new Set()
    for (const m of chat.messages)
      if (m.role === 'user' && Array.isArray(m.content)) for (const b of m.content) if (b.type === 'tool_result') ids.add(b.tool_use_id)
    return ids
  }, [chat.messages])

  return (
    <div className="page ai-page">
      <ModuleHeader
        module={{ icon: Sparkles, color: 'var(--accent)' }}
        title="PACO AI"
        subtitle="Tu asistente: consulta y organiza PACO OS por ti."
        actions={
          <>
            {usage?.daily_limit && (
              <span className="muted small ai-usage" title="Usos de hoy (cada mensaje tuyo cuenta 1)">
                Hoy: {usage.requests_today}/{usage.daily_limit}
              </span>
            )}
            <Link to="/ajustes?seccion=paco-ai" className="btn ghost sm" title="Permisos de PACO AI">
              <ShieldCheck size={15} /> <span className="hide-sm">Permisos</span>
            </Link>
            <button className="btn ghost sm" onClick={newChat} disabled={running}>
              <Plus size={15} /> <span className="hide-sm">Nueva conversación</span>
            </button>
          </>
        }
      />

      {status && !ready && <SetupNotice status={status} />}

      <div className="ai-chat card">
        <div className="ai-messages" aria-live="polite">
          {!chat.messages.length && (
            <div className="ai-empty">
              <div className="ai-empty-icon">
                <Sparkles size={26} />
              </div>
              <h3>¿En qué te ayudo?</h3>
              <p className="muted small">
                Puedo buscar en tus módulos, contarte qué tienes pendiente y crear o cambiar cosas por ti. Antes de modificar nada te pediré confirmación
                (configurable en <Link to="/ajustes?seccion=paco-ai">Ajustes</Link>).
              </p>
              <div className="ai-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chip" onClick={() => submit(s)} disabled={!ready || running}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chat.messages.map((m, i) => {
            if (m.role === 'user') {
              const text = visibleUserText(m)
              const docs = attachmentNames(m)
              if (!text && !docs.length) return null
              return (
                <div key={i} className="ai-msg user">
                  <div className="ai-user-turn">
                    {docs.length > 0 && (
                      <div className="ai-attachments">
                        {docs.map((d, j) => (
                          <span key={j} className="ai-attachment">
                            <FileText size={13} /> <span className="ellipsis">{d}</span>
                          </span>
                        ))}
                      </div>
                    )}
                    {text && <div className="ai-bubble">{text}</div>}
                  </div>
                </div>
              )
            }
            return (
              <div key={i} className="ai-msg assistant">
                <span className="ai-avatar">
                  <Sparkles size={14} />
                </span>
                <div className="ai-turn">
                  {m.content.map((b, j) => {
                    if (b.type === 'text' && b.text.trim()) return <div key={j} className="ai-bubble"><Markdown text={b.text} /></div>
                    if (b.type === 'tool_use') {
                      const info = chat.actions[b.id] || { title: TOOL_LABELS[b.name] || b.name, status: resultsById.has(b.id) ? 'done' : 'pending' }
                      return <ActionChip key={j} info={info} />
                    }
                    return null
                  })}
                </div>
              </div>
            )
          })}

          {approval && <ApprovalPanel approval={approval} onDecide={decide} onDecideAll={decideAll} />}

          {running && !approval && (
            <div className="ai-msg assistant">
              <span className="ai-avatar">
                <Sparkles size={14} />
              </span>
              <div className="ai-thinking">
                <Loader2 size={15} className="spin" /> Pensando…
              </div>
            </div>
          )}

          {notice && <p className="muted small center">{notice}</p>}

          {error && (
            <div className="notice notice-danger ai-error">
              <AlertTriangle size={18} />
              <span>{error.message || 'Ha ocurrido un error'}</span>
            </div>
          )}

          {canResume && chat.messages.length > 0 && (
            <div className="center">
              <button className="btn ghost sm" onClick={() => run(chat.messages)} disabled={!ready}>
                <RotateCcw size={15} /> {pending.length ? 'Continuar' : error ? 'Reintentar' : 'Continuar'}
              </button>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {attachments.length > 0 && (
          <div className="ai-attachments pending">
            {attachments.map((f) => (
              <span key={f.id} className="ai-attachment">
                <FileText size={13} /> <span className="ellipsis">{f.name}</span>
                <button type="button" className="icon-btn sm" onClick={() => setAttachments((a) => a.filter((x) => x.id !== f.id))} aria-label={`Quitar ${f.name}`}>
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <form
          className="ai-input"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <button
            type="button"
            className="btn ghost ai-attach"
            onClick={() => setPickerOpen(true)}
            disabled={!ready || running || pending.length > 0}
            title="Adjuntar documento (PDF o texto)"
            aria-label="Adjuntar documento"
          >
            <Paperclip size={16} />
          </button>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={ready ? 'Pregunta o pide algo… (Enter para enviar)' : 'PACO AI no está disponible todavía'}
            disabled={!ready || pending.length > 0 && !running}
            aria-label="Mensaje para PACO AI"
            maxLength={4000}
          />
          {running ? (
            <button type="button" className="btn ghost" onClick={stop} title="Detener">
              <Square size={16} /> <span className="hide-sm">Detener</span>
            </button>
          ) : (
            <button className="btn primary" disabled={!ready || !input.trim() || pending.length > 0} title="Enviar">
              <Send size={16} />
            </button>
          )}
        </form>
      </div>
      {pickerOpen && (
        <DocumentPicker
          selected={attachments}
          onClose={() => setPickerOpen(false)}
          onDone={(list) => {
            setAttachments(list)
            setPickerOpen(false)
            inputRef.current?.focus()
          }}
        />
      )}
      <p className="muted small center ai-foot">
        PACO AI puede equivocarse. Lo que consulta (y el texto de los documentos que autorices) se envía al proveedor de IA (Groq) para responderte; la conversación solo se guarda en este dispositivo.
      </p>
    </div>
  )
}

function ActionChip({ info }) {
  const Icon = info.status === 'blocked' || info.status === 'rejected' ? Ban : KIND_ICONS[info.kind] || Search
  return (
    <div className={cx('ai-action', `is-${info.status}`, info.kind === 'read' && 'is-read')}>
      <Icon size={13} />
      <span className="ellipsis">{info.title}</span>
      {info.kind !== 'read' || info.status !== 'done' ? <span className="ai-action-status">{STATUS_TEXT[info.status] || ''}</span> : <Check size={13} />}
    </div>
  )
}

function ApprovalPanel({ approval, onDecide, onDecideAll }) {
  const { actions, decisions } = approval
  return (
    <div className="ai-approval card" role="dialog" aria-label="Confirmar acciones de PACO AI">
      <p className="ai-approval-title">
        <ShieldCheck size={16} /> PACO AI quiere hacer {actions.length === 1 ? 'esto' : `${actions.length} cosas`}:
      </p>
      {actions.map((a) => (
        <div key={a.id} className={cx('ai-approval-item', a.danger && 'danger', a.id in decisions && 'decided')}>
          <div className="ai-approval-head">
            <strong>{a.title}</strong>
            {a.id in decisions ? (
              <span className="muted small">{decisions[a.id] ? 'Aprobado' : 'Rechazado'}</span>
            ) : (
              <div className="btn-row">
                <button className="btn ghost sm" onClick={() => onDecide(a.id, false)}>
                  <X size={14} /> Rechazar
                </button>
                <button className={cx('btn sm', a.danger ? 'danger' : 'primary')} onClick={() => onDecide(a.id, true)}>
                  <Check size={14} /> {a.danger ? 'Eliminar' : a.kind === 'document' ? 'Permitir leer' : 'Aprobar'}
                </button>
              </div>
            )}
          </div>
          {a.kind === 'document' && <p className="muted small ai-approval-note">Si lo permites, podrá volver a leerlo durante esta conversación.</p>}
          {a.details?.length > 0 && (
            <dl className="ai-details">
              {a.details.map((d, i) => (
                <div key={i}>
                  <dt>{d.label}</dt>
                  <dd>{d.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      ))}
      {actions.length > 1 && (
        <div className="btn-row end">
          <button className="btn ghost sm" onClick={() => onDecideAll(false)}>
            Rechazar todo
          </button>
          <button className="btn primary sm" onClick={() => onDecideAll(true)}>
            Aprobar todo
          </button>
        </div>
      )}
    </div>
  )
}

function SetupNotice({ status }) {
  let text
  if (isLocalMode || status.local)
    text =
      'PACO OS está en modo local y PACO AI necesita Supabase (la clave de la IA solo vive en el servidor).' +
      (supabaseEnvProblem
        ? ` Motivo: ${supabaseEnvProblem}. Revisa el archivo .env.local (nombre exacto, en la carpeta del proyecto y guardado en UTF-8) y reinicia npm run dev.`
        : '')
  else if (status.error) text = status.error
  else if (!status.configured) text = 'Falta configurar PACO AI en Supabase (clave de la IA y emails permitidos).'
  else if (!status.allowed) text = 'Tu cuenta no está en la lista de emails permitidos (PACO_AI_ALLOWED_EMAILS).'
  return (
    <div className="notice ai-setup">
      <AlertTriangle size={18} />
      <span>
        {text} Los pasos están en <code>docs/PACO_AI.md</code>.
      </span>
    </div>
  )
}
