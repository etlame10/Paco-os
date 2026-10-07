import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import NotificationSettings from '../components/NotificationSettings'
import AiSettings from '../components/AiSettings'
import { useInstallPrompt } from '../hooks/useInstallPrompt'
import { Settings as SettingsIcon, Sun, Moon, Laptop, Download, Upload, LogOut, KeyRound, Cloud, HardDrive, Smartphone } from 'lucide-react'
import ModuleHeader from '../components/ModuleHeader'
import { Segmented } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { api, isLocalMode } from '../lib/api'
import { COLORS } from '../lib/icons'
import { cx, downloadText, todayISO } from '../lib/utils'

export default function Settings() {
  const { user } = useAuth()
  const { settings, update } = useSettings()
  const { toast, notifyError, confirm } = useUI()
  const [password, setPassword] = useState('')
  const fileRef = useRef(null)
  const { canInstall, install } = useInstallPrompt()
  const [params] = useSearchParams()

  // /ajustes?seccion=notificaciones (desde la campana): desplaza hasta esa sección.
  useEffect(() => {
    const id = params.get('seccion')
    if (id) setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [params])

  const exportData = async () => {
    try {
      const [items, files] = await Promise.all([api.items.list(), api.files.list()])
      const payload = { app: 'PACO OS', version: 1, exported_at: new Date().toISOString(), settings, items, files }
      downloadText(`paco-os-backup-${todayISO()}.json`, JSON.stringify(payload, null, 2))
      toast('Copia de seguridad descargada')
    } catch (e) {
      notifyError(e)
    }
  }

  const importData = async (file) => {
    try {
      const json = JSON.parse(await file.text())
      if (!Array.isArray(json.items)) throw new Error('El archivo no es una copia de PACO OS válida')
      const ok = await confirm(`Se importarán ${json.items.length} elementos (se añaden a los existentes).`, {
        title: 'Importar copia',
        confirmText: 'Importar',
        danger: false,
      })
      if (!ok) return
      const rows = json.items.map(({ module, title, body, status, due_date, tags, data, pinned, position }) => ({
        module, title, body, status, due_date, tags, data, pinned, position,
      }))
      for (let i = 0; i < rows.length; i += 200) await api.items.bulkInsert(rows.slice(i, i + 200))
      if (json.settings?.customModules?.length) {
        update((prev) => {
          const ids = new Set(prev.customModules.map((m) => m.id))
          const extra = json.settings.customModules.filter((m) => !ids.has(m.id))
          return {
            customModules: [...prev.customModules, ...extra],
            enabledModules: [...new Set([...prev.enabledModules, ...extra.map((m) => m.id)])],
          }
        })
      }
      toast(`${rows.length} elementos importados`)
    } catch (e) {
      notifyError(e)
    }
  }

  const changePassword = async (e) => {
    e.preventDefault()
    try {
      await api.auth.updatePassword(password)
      setPassword('')
      toast('Contraseña actualizada')
    } catch (err) {
      notifyError(err)
    }
  }

  return (
    <div className="page settings-page">
      <ModuleHeader module={{ icon: SettingsIcon, color: 'var(--accent)' }} title="Ajustes" subtitle="Personaliza PACO OS a tu gusto." />

      <section className="card settings-section">
        <h3 className="section-title">Perfil</h3>
        <div className="field">
          <label>¿Cómo quieres que te llame?</label>
          <input value={settings.displayName} onChange={(e) => update({ displayName: e.target.value })} placeholder="Paco" />
        </div>
        <p className="muted small">Sesión: {user?.email}</p>
      </section>

      <section className="card settings-section">
        <h3 className="section-title">Apariencia</h3>
        <div className="field">
          <label>Tema</label>
          <Segmented
            value={settings.theme}
            onChange={(theme) => update({ theme })}
            options={[
              { value: 'dark', label: 'Oscuro', icon: Moon },
              { value: 'light', label: 'Claro', icon: Sun },
              { value: 'system', label: 'Sistema', icon: Laptop },
            ]}
          />
        </div>
        <div className="field">
          <label>Color de acento</label>
          <div className="color-picker">
            {COLORS.map((c) => (
              <button key={c} style={{ background: c }} className={cx(settings.accent === c && 'active')} onClick={() => update({ accent: c })} aria-label={c} />
            ))}
          </div>
        </div>
      </section>

      <NotificationSettings />

      <AiSettings />

      <section className="card settings-section">
        <h3 className="section-title">Datos</h3>
        <div className="notice">
          {isLocalMode ? <HardDrive size={18} /> : <Cloud size={18} />}
          <span>
            {isLocalMode
              ? 'Modo local: tus datos están solo en este navegador. Configura Supabase (ver README) para sincronizarlos entre todos tus dispositivos.'
              : 'Conectado a Supabase: tus datos se sincronizan en todos tus dispositivos.'}
          </span>
        </div>
        <div className="btn-row">
          <button className="btn ghost" onClick={exportData}>
            <Download size={16} /> Exportar copia (JSON)
          </button>
          <button className="btn ghost" onClick={() => fileRef.current?.click()}>
            <Upload size={16} /> Importar copia
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const f = e.target.files[0]
              e.target.value = ''
              if (f) importData(f)
            }}
          />
        </div>
        <p className="muted small">La copia incluye todos los elementos de tus módulos y la lista de archivos (no el contenido de los archivos).</p>
      </section>

      <section className="card settings-section">
        <h3 className="section-title">
          <Smartphone size={16} /> Instalar como app
        </h3>
        <p className="muted small">
          En el móvil: abre PACO OS en el navegador y usa <strong>«Añadir a pantalla de inicio»</strong> (Safari: botón compartir · Chrome: menú ⋮
          → Instalar app). En el PC (Chrome/Edge): icono de instalar en la barra de direcciones. Se abrirá como una aplicación más.
          En iPhone/iPad, las notificaciones solo funcionan con la app instalada así (iOS 16.4 o superior).
        </p>
        {canInstall && (
          <button className="btn ghost sm" onClick={install}>
            <Download size={15} /> Instalar ahora
          </button>
        )}
      </section>

      <section className="card settings-section">
        <h3 className="section-title">Cuenta</h3>
        {!isLocalMode && (
          <form className="btn-row" onSubmit={changePassword}>
            <div className="input-icon grow">
              <KeyRound size={16} />
              <input type="password" minLength={6} required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Nueva contraseña" autoComplete="new-password" />
            </div>
            <button className="btn ghost">Cambiar contraseña</button>
          </form>
        )}
        <button className="btn danger" onClick={() => api.auth.signOut()}>
          <LogOut size={16} /> Cerrar sesión
        </button>
      </section>

      <p className="muted small center">PACO OS v1.0 · Hecho con React, Vite y Supabase</p>
    </div>
  )
}
