import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, CalendarDays, Puzzle, Settings, Search, Menu, X, HardDrive, LogOut } from 'lucide-react'
import { Logo } from './Logo'
import CommandPalette from './CommandPalette'
import { useSettings } from '../context/SettingsContext'
import { useAuth } from '../context/AuthContext'
import { api, isLocalMode } from '../lib/api'
import { cx } from '../lib/utils'

export default function Layout() {
  const { enabledModules, settings } = useSettings()
  const { user } = useAuth()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()

  useEffect(() => setDrawer(false), [location.pathname])

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const name = settings.displayName || user?.email?.split('@')[0]

  const nav = (
    <>
      <NavLink to="/" end className="nav-link">
        <LayoutDashboard size={18} /> <span>Inicio</span>
      </NavLink>
      <NavLink to="/calendario" className="nav-link">
        <CalendarDays size={18} /> <span>Calendario</span>
      </NavLink>
      <div className="nav-label">Módulos</div>
      {enabledModules.map((m) => (
        <NavLink key={m.id} to={`/m/${m.id}`} className="nav-link" style={{ '--mod': m.color }}>
          <m.icon size={18} className="nav-mod-icon" /> <span>{m.name}</span>
        </NavLink>
      ))}
      <NavLink to="/modulos" className="nav-link subtle">
        <Puzzle size={18} /> <span>Gestionar módulos</span>
      </NavLink>
    </>
  )

  return (
    <div className="app">
      <aside className={cx('sidebar', drawer && 'open')}>
        <div className="sidebar-top">
          <NavLink to="/" className="brand">
            <Logo size={30} />
            <span>PACO OS</span>
          </NavLink>
          <button className="icon-btn show-sm" onClick={() => setDrawer(false)} aria-label="Cerrar menú">
            <X size={18} />
          </button>
        </div>
        <button className="search-trigger" onClick={() => setPaletteOpen(true)}>
          <Search size={16} /> <span>Buscar…</span> <kbd>Ctrl K</kbd>
        </button>
        <nav className="nav">{nav}</nav>
        <div className="sidebar-bottom">
          {isLocalMode && (
            <div className="local-pill" title="Los datos se guardan solo en este navegador">
              <HardDrive size={14} /> Modo local
            </div>
          )}
          <NavLink to="/ajustes" className="nav-link">
            <Settings size={18} /> <span className="ellipsis">{name || 'Ajustes'}</span>
          </NavLink>
          <button className="nav-link" onClick={() => api.auth.signOut()}>
            <LogOut size={18} /> <span>Salir</span>
          </button>
        </div>
      </aside>
      {drawer && <div className="drawer-backdrop" onClick={() => setDrawer(false)} />}

      <div className="main">
        <header className="mobile-top">
          <button className="icon-btn" onClick={() => setDrawer(true)} aria-label="Abrir menú">
            <Menu size={20} />
          </button>
          <NavLink to="/" className="brand">
            <Logo size={26} />
            <span>PACO OS</span>
          </NavLink>
          <button className="icon-btn" onClick={() => setPaletteOpen(true)} aria-label="Buscar">
            <Search size={20} />
          </button>
        </header>
        <main className="content">
          <Outlet />
        </main>
        <nav className="bottom-nav">
          <NavLink to="/" end>
            <LayoutDashboard size={20} />
            <span>Inicio</span>
          </NavLink>
          {enabledModules.slice(0, 3).map((m) => (
            <NavLink key={m.id} to={`/m/${m.id}`} style={{ '--mod': m.color }}>
              <m.icon size={20} />
              <span>{m.name.split(' ')[0]}</span>
            </NavLink>
          ))}
          <button onClick={() => setDrawer(true)}>
            <Menu size={20} />
            <span>Más</span>
          </button>
        </nav>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
