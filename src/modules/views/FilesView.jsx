import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Upload, FolderPlus, Folder, FolderOpen, File, FileText, FileImage, FileVideo, FileAudio, FileArchive,
  Download, Pencil, Trash2, Search, LayoutGrid, List, ChevronRight, Eye, FolderInput, Home,
} from 'lucide-react'
import ModuleHeader, { SummaryChips } from '../../components/ModuleHeader'
import Modal from '../../components/Modal'
import { EmptyState, Segmented, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import { useUI } from '../../context/UIContext'
import { useSettings } from '../../context/SettingsContext'
import { cx, formatBytes, timeAgo } from '../../lib/utils'

function fileKind(f) {
  const t = f.mime_type || ''
  const n = f.name.toLowerCase()
  if (t.startsWith('image/')) return 'image'
  if (t.startsWith('video/')) return 'video'
  if (t.startsWith('audio/')) return 'audio'
  if (t === 'application/pdf' || n.endsWith('.pdf')) return 'pdf'
  if (t.startsWith('text/') || /\.(md|txt|csv|json|js|py|html|css)$/.test(n)) return 'text'
  if (/\.(zip|rar|7z|tar|gz)$/.test(n)) return 'archive'
  return 'other'
}
const KIND_ICON = { image: FileImage, video: FileVideo, audio: FileAudio, pdf: FileText, text: FileText, archive: FileArchive, other: File }
const KIND_COLOR = { image: '#ec4899', video: '#f97316', audio: '#a855f7', pdf: '#ef4444', text: '#3b82f6', archive: '#eab308', other: '#64748b' }

export default function FilesView({ module }) {
  const { notifyError, toast, confirm } = useUI()
  const { settings, update: updateSettings } = useSettings()
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [folder, setFolder] = useState('')
  const [query, setQuery] = useState('')
  const [view, setView] = useState(() => localStorage.getItem('pacoos.files.view') || 'grid')
  const [uploads, setUploads] = useState([])
  const [dragging, setDragging] = useState(false)
  const [preview, setPreview] = useState(null)
  const [dialog, setDialog] = useState(null) // {type:'folder'|'rename'|'move', file}
  const inputRef = useRef(null)

  useEffect(() => localStorage.setItem('pacoos.files.view', view), [view])

  const load = useCallback(async () => {
    try {
      setFiles(await api.files.list())
    } catch (e) {
      notifyError(e)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    load()
  }, [load])

  const folders = useMemo(() => {
    const set = new Set([...(settings.fileFolders || []), ...files.map((f) => f.folder).filter(Boolean)])
    return [...set].sort((a, b) => a.localeCompare(b, 'es'))
  }, [files, settings.fileFolders])

  const visible = useMemo(() => {
    const q = query.toLowerCase().trim()
    if (q) return files.filter((f) => f.name.toLowerCase().includes(q))
    return files.filter((f) => (f.folder || '') === folder)
  }, [files, folder, query])

  const totalSize = files.reduce((a, f) => a + (f.size || 0), 0)

  const uploadFiles = async (list) => {
    const arr = [...list]
    if (!arr.length) return
    for (const file of arr) {
      const id = crypto.randomUUID()
      setUploads((u) => [...u, { id, name: file.name }])
      try {
        const row = await api.files.upload(file, folder)
        setFiles((f) => [row, ...f])
      } catch (e) {
        notifyError(e)
      } finally {
        setUploads((u) => u.filter((x) => x.id !== id))
      }
    }
    toast(arr.length === 1 ? 'Archivo subido' : `${arr.length} archivos subidos`)
  }

  const open = async (f) => {
    try {
      const url = await api.files.getUrl(f)
      setPreview({ file: f, url, kind: fileKind(f) })
    } catch (e) {
      notifyError(e)
    }
  }

  const download = async (f) => {
    try {
      const url = await api.files.getUrl(f, { download: true })
      const a = document.createElement('a')
      a.href = url
      a.download = f.name
      a.target = '_blank'
      a.rel = 'noreferrer'
      a.click()
    } catch (e) {
      notifyError(e)
    }
  }

  const patchFile = async (f, patch) => {
    try {
      const row = await api.files.update(f.id, patch)
      setFiles((all) => all.map((x) => (x.id === f.id ? row : x)))
    } catch (e) {
      notifyError(e)
    }
  }

  const del = async (f) => {
    if (!(await confirm(`Se eliminará "${f.name}" de forma permanente.`))) return
    try {
      await api.files.remove(f)
      setFiles((all) => all.filter((x) => x.id !== f.id))
      setPreview(null)
      toast('Archivo eliminado')
    } catch (e) {
      notifyError(e)
    }
  }

  const deleteFolder = async (name) => {
    if (files.some((f) => f.folder === name)) return toast('La carpeta no está vacía', 'info')
    updateSettings((p) => ({ fileFolders: (p.fileFolders || []).filter((x) => x !== name) }))
    setFolder('')
  }

  return (
    <div
      className={cx('page files-page', dragging && 'dragging')}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes('Files')) {
          e.preventDefault()
          setDragging(true)
        }
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        uploadFiles(e.dataTransfer.files)
      }}
    >
      <ModuleHeader
        module={module}
        actions={
          <>
            <button className="btn ghost" onClick={() => setDialog({ type: 'folder' })}>
              <FolderPlus size={18} /> <span className="hide-sm">Carpeta</span>
            </button>
            <button className="btn primary" onClick={() => inputRef.current?.click()}>
              <Upload size={18} /> <span className="hide-sm">Subir</span>
            </button>
            <input ref={inputRef} type="file" multiple hidden onChange={(e) => uploadFiles(e.target.files).then(() => (e.target.value = ''))} />
          </>
        }
      />

      <SummaryChips
        stats={[
          { label: 'Archivos', value: files.length },
          { label: 'Carpetas', value: folders.length },
          { label: 'Espacio usado', value: formatBytes(totalSize) },
        ]}
      />

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar en todos los archivos…" />
        </div>
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: 'grid', icon: LayoutGrid, title: 'Cuadrícula' },
            { value: 'list', icon: List, title: 'Lista' },
          ]}
        />
      </div>

      {!query && (
        <nav className="breadcrumb">
          <button onClick={() => setFolder('')} className={cx(!folder && 'active')}>
            <Home size={14} /> Todos
          </button>
          {folder && (
            <>
              <ChevronRight size={14} className="muted" />
              <button className="active">{folder}</button>
              <span className="spacer" />
              {!files.some((f) => f.folder === folder) && (
                <button className="btn ghost xs danger-text" onClick={() => deleteFolder(folder)}>
                  <Trash2 size={13} /> Borrar carpeta
                </button>
              )}
            </>
          )}
        </nav>
      )}

      {uploads.length > 0 && (
        <div className="uploads">
          {uploads.map((u) => (
            <div key={u.id} className="upload-row">
              <Spinner size={14} /> Subiendo {u.name}…
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <Spinner label="Cargando archivos…" />
      ) : (
        <>
          {!folder && !query && folders.length > 0 && (
            <div className="folders">
              {folders.map((name) => (
                <button key={name} className="folder-card" onClick={() => setFolder(name)}>
                  <Folder size={20} />
                  <span>{name}</span>
                  <small className="muted">{files.filter((f) => f.folder === name).length}</small>
                </button>
              ))}
            </div>
          )}
          {!visible.length ? (
            <div className="dropzone" onClick={() => inputRef.current?.click()}>
              <EmptyState
                icon={query ? Search : FolderOpen}
                title={query ? 'Sin resultados' : folder ? 'Carpeta vacía' : 'Sin archivos todavía'}
                text={query ? 'No hay archivos con ese nombre.' : 'Arrastra archivos aquí o pulsa para subirlos.'}
              />
            </div>
          ) : (
            <div className={view === 'grid' ? 'file-grid' : 'list'}>
              {visible.map((f) => (
                <FileTile
                  key={f.id}
                  file={f}
                  view={view}
                  onOpen={() => open(f)}
                  onDownload={() => download(f)}
                  onRename={() => setDialog({ type: 'rename', file: f })}
                  onMove={() => setDialog({ type: 'move', file: f })}
                  onDelete={() => del(f)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {dragging && (
        <div className="drop-overlay">
          <Upload size={40} />
          <p>Suelta para subir {folder ? `a "${folder}"` : ''}</p>
        </div>
      )}

      {preview && (
        <Modal title={preview.file.name} onClose={() => setPreview(null)} size="lg">
          <div className="preview">
            {preview.kind === 'image' && <img src={preview.url} alt={preview.file.name} />}
            {preview.kind === 'video' && <video src={preview.url} controls />}
            {preview.kind === 'audio' && <audio src={preview.url} controls />}
            {(preview.kind === 'pdf' || preview.kind === 'text') && <iframe src={preview.url} title={preview.file.name} />}
            {['archive', 'other'].includes(preview.kind) && (
              <EmptyState icon={File} title="Vista previa no disponible" text="Descarga el archivo para abrirlo." />
            )}
          </div>
          <div className="modal-actions">
            <span className="muted small">
              {formatBytes(preview.file.size)} · {timeAgo(preview.file.created_at)}
            </span>
            <span className="spacer" />
            <button className="btn ghost danger-text" onClick={() => del(preview.file)}>
              <Trash2 size={16} /> Eliminar
            </button>
            <button className="btn primary" onClick={() => download(preview.file)}>
              <Download size={16} /> Descargar
            </button>
          </div>
        </Modal>
      )}

      {dialog?.type === 'folder' && (
        <PromptDialog
          title="Nueva carpeta"
          label="Nombre de la carpeta"
          onClose={() => setDialog(null)}
          onSubmit={(name) => {
            updateSettings((p) => ({ fileFolders: [...new Set([...(p.fileFolders || []), name])] }))
            setFolder(name)
          }}
        />
      )}
      {dialog?.type === 'rename' && (
        <PromptDialog
          title="Renombrar archivo"
          label="Nuevo nombre"
          initial={dialog.file.name}
          onClose={() => setDialog(null)}
          onSubmit={(name) => patchFile(dialog.file, { name })}
        />
      )}
      {dialog?.type === 'move' && (
        <Modal title={`Mover "${dialog.file.name}"`} onClose={() => setDialog(null)} size="sm">
          <div className="move-list">
            {['', ...folders].map((name) => (
              <button
                key={name || '__root'}
                className={cx('row', (dialog.file.folder || '') === name && 'active')}
                onClick={() => {
                  patchFile(dialog.file, { folder: name })
                  setDialog(null)
                  toast('Archivo movido')
                }}
              >
                {name ? <Folder size={16} /> : <Home size={16} />} {name || 'Sin carpeta'}
              </button>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

function FileTile({ file, view, onOpen, onDownload, onRename, onMove, onDelete }) {
  const kind = fileKind(file)
  const Icon = KIND_ICON[kind]
  const actions = (
    <div className="item-actions" onClick={(e) => e.stopPropagation()}>
      <button className="icon-btn sm" onClick={onOpen} title="Ver">
        <Eye size={15} />
      </button>
      <button className="icon-btn sm" onClick={onDownload} title="Descargar">
        <Download size={15} />
      </button>
      <button className="icon-btn sm" onClick={onRename} title="Renombrar">
        <Pencil size={15} />
      </button>
      <button className="icon-btn sm" onClick={onMove} title="Mover">
        <FolderInput size={15} />
      </button>
      <button className="icon-btn sm danger-text" onClick={onDelete} title="Eliminar">
        <Trash2 size={15} />
      </button>
    </div>
  )
  if (view === 'list') {
    return (
      <div className="row" onClick={onOpen}>
        <Icon size={20} style={{ color: KIND_COLOR[kind] }} />
        <div className="row-main">
          <div className="row-title ellipsis">{file.name}</div>
          <div className="item-meta">
            <span className="meta">{formatBytes(file.size)}</span>
            <span className="meta">{timeAgo(file.created_at)}</span>
            {file.folder && <span className="meta">📁 {file.folder}</span>}
          </div>
        </div>
        {actions}
      </div>
    )
  }
  return (
    <div className="card file-tile" onClick={onOpen}>
      <div className="file-icon" style={{ '--kind': KIND_COLOR[kind] }}>
        <Icon size={30} />
      </div>
      <div className="file-name" title={file.name}>
        {file.name}
      </div>
      <div className="muted small">{formatBytes(file.size)}</div>
      {actions}
    </div>
  )
}

export function PromptDialog({ title, label, initial = '', onSubmit, onClose }) {
  const [v, setV] = useState(initial)
  return (
    <Modal title={title} onClose={onClose} size="sm">
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault()
          if (!v.trim()) return
          onSubmit(v.trim())
          onClose()
        }}
      >
        <div className="field">
          <label>{label}</label>
          <input autoFocus value={v} onChange={(e) => setV(e.target.value)} onFocus={(e) => e.target.select()} />
        </div>
        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn primary">Aceptar</button>
        </div>
      </form>
    </Modal>
  )
}
