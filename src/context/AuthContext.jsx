import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined) // undefined = cargando

  useEffect(() => {
    let alive = true
    api.auth.getSession().then((s) => alive && setSession(s ?? null))
    const off = api.auth.onChange((s) => setSession(s ?? null))
    return () => {
      alive = false
      off()
    }
  }, [])

  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, loading: session === undefined }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
