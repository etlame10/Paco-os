import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { SettingsProvider, useSettings } from './context/SettingsContext'
import { UIProvider } from './context/UIContext'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import ResetPassword from './pages/ResetPassword'
import Dashboard from './pages/Dashboard'
import Calendar from './pages/Calendar'
import ModulePage from './pages/ModulePage'
import ModulesStore from './pages/ModulesStore'
import Settings from './pages/Settings'
import Assistant from './pages/Assistant'
import ConfigError from './pages/ConfigError'
import { supabaseConfigError } from './lib/supabase'

function Gate() {
  const { session, loading, recovery } = useAuth()
  const { loaded } = useSettings()

  if (loading) return <FullScreenLoader />
  if (!session) return <Login />
  if (recovery) return <ResetPassword />
  if (!loaded) return <FullScreenLoader />

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="calendario" element={<Calendar />} />
        <Route path="ai" element={<Assistant />} />
        <Route path="m/:moduleId" element={<ModulePage />} />
        <Route path="modulos" element={<ModulesStore />} />
        <Route path="ajustes" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

function FullScreenLoader() {
  return (
    <div className="fullscreen-center">
      <Spinner size={28} label="Cargando PACO OS…" />
    </div>
  )
}

// HashRouter: las rutas van tras "#", así funciona en GitHub Pages sin configurar el servidor.
export default function App() {
  // Clave de Supabase peligrosa (secreta) en el build: no se arranca nada más.
  if (supabaseConfigError) return <ConfigError message={supabaseConfigError} />

  return (
    <HashRouter>
      <UIProvider>
        <AuthProvider>
          <SettingsProvider>
            <Gate />
          </SettingsProvider>
        </AuthProvider>
      </UIProvider>
    </HashRouter>
  )
}
