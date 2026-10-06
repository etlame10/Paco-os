import { useState } from 'react'
import { Mail, KeyRound, Sparkles, HardDrive } from 'lucide-react'
import { api, isLocalMode } from '../lib/api'
import { Logo } from '../components/Logo'

export default function Login() {
  const [mode, setMode] = useState('login') // login | signup | magic | reset
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try {
      if (mode === 'login') await api.auth.signIn(email, password)
      if (mode === 'signup') {
        const res = await api.auth.signUp(email, password)
        if (!res?.session) setMsg({ ok: true, text: 'Cuenta creada. Revisa tu correo para confirmarla y después inicia sesión.' })
      }
      if (mode === 'magic') {
        await api.auth.magicLink(email)
        setMsg({ ok: true, text: 'Te hemos enviado un enlace mágico. Ábrelo desde este dispositivo.' })
      }
      if (mode === 'reset') {
        await api.auth.resetPassword(email)
        setMsg({ ok: true, text: 'Si el correo existe, recibirás un enlace para cambiar la contraseña.' })
      }
    } catch (err) {
      const t = err.message || 'Error'
      setMsg({
        ok: false,
        text: /invalid login/i.test(t) ? 'Correo o contraseña incorrectos.' : /not confirmed/i.test(t)
              ? 'Debes confirmar tu correo antes de entrar.'
              : /failed to fetch|network/i.test(t)
                ? 'No se pudo conectar con el servidor. Revisa tu conexión o la configuración de Supabase.'
                : t,
      })
    } finally {
      setBusy(false)
    }
  }

  const titles = { login: 'Inicia sesión', signup: 'Crea tu cuenta', magic: 'Entrar sin contraseña', reset: 'Recuperar contraseña' }

  return (
    <div className="auth-screen">
      <div className="auth-glow" />
      <div className="auth-card">
        <Logo size={48} />
        <h1>PACO OS</h1>
        <p className="muted">Tu centro digital personal</p>

        {isLocalMode ? (
          <>
            <div className="notice">
              <HardDrive size={18} />
              <span>
                Supabase aún no está configurado. Puedes usar PACO OS en <strong>modo local</strong>: los datos se guardan solo en este navegador.
              </span>
            </div>
            <button className="btn primary block" onClick={() => api.auth.signIn()}>
              <Sparkles size={18} /> Entrar en modo local
            </button>
          </>
        ) : (
          <form onSubmit={submit} className="form">
            <h2>{titles[mode]}</h2>
            <div className="field">
              <label htmlFor="email">Correo electrónico</label>
              <div className="input-icon">
                <Mail size={16} />
                <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </div>
            {(mode === 'login' || mode === 'signup') && (
              <div className="field">
                <label htmlFor="password">Contraseña</label>
                <div className="input-icon">
                  <KeyRound size={16} />
                  <input
                    id="password"
                    type="password"
                    required
                    minLength={6}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>
            )}
            {msg && <p className={msg.ok ? 'form-ok' : 'form-error'}>{msg.text}</p>}
            <button className="btn primary block" disabled={busy}>
              {busy ? 'Un momento…' : mode === 'login' ? 'Entrar' : mode === 'signup' ? 'Crear cuenta' : 'Enviar enlace'}
            </button>
            <div className="auth-links">
              {mode !== 'login' && <button type="button" onClick={() => setMode('login')}>Ya tengo cuenta</button>}
              {mode !== 'signup' && <button type="button" onClick={() => setMode('signup')}>Crear cuenta</button>}
              {mode !== 'magic' && <button type="button" onClick={() => setMode('magic')}>Enlace mágico</button>}
              {mode === 'login' && <button type="button" onClick={() => setMode('reset')}>¿Olvidaste la contraseña?</button>}
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
