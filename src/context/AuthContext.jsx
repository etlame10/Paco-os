import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined) // undefined = cargando
  // true cuando el usuario llega desde el enlace "recuperar contraseña" del correo
  const [recovery, setRecovery] = useState(false)

  useEffect(() => {
    let alive = true
    api.auth.getSession().then((s) => alive && setSession((prev) => (prev === undefined ? s ?? null : prev)))
    const off = api.auth.onChange((s, event) => {
      setSession(s ?? null)
      if (event === 'PASSWORD_RECOVERY') setRecovery(true)
      if (event === 'SIGNED_OUT') setRecovery(false)
    })
    return () => {
      alive = false
      off()
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        loading: session === undefined,
        recovery,
        endRecovery: () => setRecovery(false),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
