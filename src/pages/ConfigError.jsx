import { ShieldAlert } from 'lucide-react'
import { Logo } from '../components/Logo'

// Pantalla de bloqueo si la web se ha construido con una clave secreta de Supabase.
export default function ConfigError({ message }) {
  return (
    <div className="auth-screen">
      <div className="auth-glow" />
      <div className="auth-card">
        <Logo size={48} />
        <h1>PACO OS</h1>
        <div className="notice notice-danger" role="alert">
          <ShieldAlert size={18} />
          <span>{message}</span>
        </div>
      </div>
    </div>
  )
}
