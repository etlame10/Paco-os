import { useEffect, useRef, useState } from 'react'
import { FileText, Upload, Check } from 'lucide-react'
import Modal from './Modal'
import { Spinner } from './ui'
import { useUI } from '../context/UIContext'
import { api } from '../lib/api'
import { DOC_MAX_BYTES, documentKind } from '../lib/ai/documents'
import { cx, formatBytes, timeAgo } from '../lib/utils'

// Elegir qué documentos puede leer PACO AI: de los ya subidos a Archivos (Supabase
// Storage) o subiendo uno nuevo, que se guarda en Archivos como cualquier otro.
// Adjuntar un documento = autorizar a PACO AI a leerlo en esta conversación.
export default function DocumentPicker({ selected, onDone, onClose }) {
  const { notifyError } = useUI()
  const [files, setFiles] = useState(null)
  const [picked, setPicked] = useState(() => new Set(selected.map((f) => f.id)))
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    api.files
      .list()
      .then((all) => setFiles(all.filter((f) => documentKind(f))))
      .catch((e) => {
        notifyError(e)
        setFiles([])
      })
  }, [notifyError])

  const toggle = (id) =>
    setPicked((p) => {
      const n = new Set(p)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })

  const upload = async (file) => {
    if (!documentKind({ name: file.name, mime_type: file.type })) return notifyError(new Error('Solo se pueden adjuntar PDF o archivos de texto.'))
    if (file.size > DOC_MAX_BYTES) return notifyError(new Error(`El archivo supera ${DOC_MAX_BYTES / 1024 / 1024} MB.`))
    setUploading(true)
    try {
      const row = await api.files.upload(file)
      setFiles((f) => [row, ...(f || [])])
      setPicked((p) => new Set([...p, row.id]))
    } catch (e) {
      notifyError(e)
    } finally {
      setUploading(false)
    }
  }

  const done = () => onDone((files || []).filter((f) => picked.has(f.id)))

  return (
    <Modal title="Adjuntar documentos" onClose={onClose}>
      <p className="muted small">
        PACO AI podrá leer el texto de los documentos que adjuntes (solo en esta conversación) y se enviará a Gemini para responderte. PDF o texto,
        hasta {DOC_MAX_BYTES / 1024 / 1024} MB.
      </p>
      <button className="btn ghost sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
        <Upload size={15} /> {uploading ? 'Subiendo…' : 'Subir un documento nuevo'}
      </button>
      <input
        ref={fileRef}
        type="file"
        hidden
        accept="application/pdf,.pdf,text/plain,.txt,.md,.csv,.json"
        onChange={(e) => {
          const f = e.target.files[0]
          e.target.value = ''
          if (f) upload(f)
        }}
      />
      <div className="doc-list">
        {files === null ? (
          <Spinner label="Cargando tus archivos…" />
        ) : files.length === 0 ? (
          <p className="muted small">Aún no tienes PDF ni documentos de texto en Archivos.</p>
        ) : (
          files.map((f) => (
            <button key={f.id} type="button" className={cx('doc-row', picked.has(f.id) && 'on')} onClick={() => toggle(f.id)} aria-pressed={picked.has(f.id)}>
              <FileText size={16} />
              <span className="ellipsis">{f.name}</span>
              <span className="muted small">
                {formatBytes(f.size)} · {timeAgo(f.created_at)}
              </span>
              <span className="doc-check">{picked.has(f.id) && <Check size={14} />}</span>
            </button>
          ))
        )}
      </div>
      <div className="modal-actions">
        <button className="btn ghost" onClick={onClose}>
          Cancelar
        </button>
        <button className="btn primary" onClick={done} disabled={uploading}>
          Adjuntar {picked.size ? `(${picked.size})` : ''}
        </button>
      </div>
    </Modal>
  )
}
