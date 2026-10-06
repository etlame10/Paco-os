import { useState } from 'react'
import { KeyRound } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { Logo } from '../components/Logo'

// Se muestra al abrir el enlace de "recuperar contraseña" enviado por Supabase Auth.
export default function ResetPassword() {
  const { endRecovery } = useAuth()
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (password !== repeat) return setError('Las contraseñas no coinciden.')
    setBusy(true)
    setError('')
    try {
      await api.auth.updatePassword(password)
      endRecovery()
    } catch (err) {
      setError(err.message || 'No se pudo cambiar la contraseña.')
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-glow" />
      <div className="auth-card">
        <Logo size={48} />
        <h1>PACO OS</h1>
        <form onSubmit={submit} className="form">
          <h2>Elige una nueva contraseña</h2>
          {[
            ['new-password', 'Nueva contraseña', password, setPassword],
            ['repeat-password', 'Repite la contraseña', repeat, setRepeat],
          ].map(([id, label, value, set]) => (
            <div key={id} className="field">
              <label htmlFor={id}>{label}</label>
              <div className="input-icon">
                <KeyRound size={16} />
                <input id={id} type="password" required minLength={6} autoComplete="new-password" value={value} onChange={(e) => set(e.target.value)} />
              </div>
            </div>
          ))}
          {error && <p className="form-error">{error}</p>}
          <button className="btn primary block" disabled={busy}>
            {busy ? 'Guardando…' : 'Guardar contraseña'}
          </button>
          <div className="auth-links">
            <button type="button" onClick={endRecovery}>
              Ahora no
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
