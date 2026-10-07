import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, rawBackend } from '../lib/api'
import { useAuth } from './AuthContext'
import { STATIC_MODULES, DEFAULT_ENABLED, buildCustomModule } from '../modules/registry'
import { getNotificationPrefs } from '../lib/notifications/prefs'
import { resyncAllNotifications, setNotificationContext } from '../lib/notifications/sync'

// Sube este número si cambian las reglas de avisos y hay que reprogramar todo una vez.
const NOTIFICATIONS_VERSION = 1

const SettingsContext = createContext(null)

export const DEFAULT_SETTINGS = {
  displayName: '',
  theme: 'dark', // 'dark' | 'light' | 'system'
  accent: '#7c5cff',
  enabledModules: DEFAULT_ENABLED,
  moduleOrder: [],
  customModules: [],
}

function applyTheme(settings) {
  const root = document.documentElement
  const dark =
    settings.theme === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
      : settings.theme !== 'light'
  root.dataset.theme = dark ? 'dark' : 'light'
  root.style.setProperty('--accent', settings.accent)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0b0d12' : '#f6f7fb')
}

export function SettingsProvider({ children }) {
  const { user } = useAuth()
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [loaded, setLoaded] = useState(false)
  const saveTimer = useRef(null)

  useEffect(() => {
    if (!user) {
      setLoaded(false)
      return
    }
    let alive = true
    api.settings
      .get()
      .then((s) => alive && setSettings({ ...DEFAULT_SETTINGS, ...(s || {}) }))
      .catch((e) => console.error('No se pudieron cargar los ajustes', e))
      .finally(() => alive && setLoaded(true))
    return () => {
      alive = false
    }
  }, [user])

  useEffect(() => {
    applyTheme(settings)
    if (settings.theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const fn = () => applyTheme(settings)
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [settings])

  const update = useCallback((patch) => {
    setSettings((prev) => {
      const next = { ...prev, ...(typeof patch === 'function' ? patch(prev) : patch) }
      clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(() => {
        api.settings.save(next).catch((e) => console.error('No se pudieron guardar los ajustes', e))
      }, 400)
      return next
    })
  }, [])

  const modules = useMemo(
    () => [...STATIC_MODULES, ...settings.customModules.map(buildCustomModule)],
    [settings.customModules],
  )

  const enabledModules = useMemo(() => {
    const enabled = modules.filter((m) => settings.enabledModules.includes(m.id))
    const order = settings.moduleOrder
    return enabled.sort((a, b) => {
      const ia = order.indexOf(a.id)
      const ib = order.indexOf(b.id)
      if (ia === -1 && ib === -1) return modules.indexOf(a) - modules.indexOf(b)
      if (ia === -1) return 1
      if (ib === -1) return -1
      return ia - ib
    })
  }, [modules, settings.enabledModules, settings.moduleOrder])

  const getModule = useCallback((id) => modules.find((m) => m.id === id), [modules])

  const toggleModule = useCallback(
    (id, on) =>
      update((prev) => ({
        enabledModules: on
          ? [...new Set([...prev.enabledModules, id])]
          : prev.enabledModules.filter((x) => x !== id),
      })),
    [update],
  )

  const moveModule = useCallback(
    (id, dir) => {
      const ids = enabledModules.map((m) => m.id)
      const i = ids.indexOf(id)
      const j = i + dir
      if (i < 0 || j < 0 || j >= ids.length) return
      ;[ids[i], ids[j]] = [ids[j], ids[i]]
      update({ moduleOrder: ids })
    },
    [enabledModules, update],
  )

  // ---- Notificaciones ----
  // La capa de datos necesita conocer los módulos y ajustes para programar avisos.
  setNotificationContext({ getModule, settings })

  const notificationPrefs = useMemo(() => getNotificationPrefs(settings), [settings])
  const prefsKey = JSON.stringify(notificationPrefs)
  const lastPrefsKey = useRef(null)

  useEffect(() => {
    if (!loaded || !user) return
    // Primera carga tras activar el sistema de avisos: programa los avisos de los elementos
    // que ya existían (solo crea avisos, no modifica ningún elemento).
    if (settings.notificationsVersion !== NOTIFICATIONS_VERSION) {
      lastPrefsKey.current = prefsKey
      resyncAllNotifications(rawBackend)
        .then(() => update({ notificationsVersion: NOTIFICATIONS_VERSION }))
        .catch((e) => console.warn('[PACO OS] No se pudieron programar los avisos', e))
      return
    }
    if (lastPrefsKey.current === null) {
      lastPrefsKey.current = prefsKey
      return
    }
    if (lastPrefsKey.current === prefsKey) return
    // Cambió una hora por defecto, la zona horaria...: se recalculan los avisos futuros.
    const t = setTimeout(() => {
      lastPrefsKey.current = prefsKey
      resyncAllNotifications(rawBackend).catch((e) => console.warn('[PACO OS] No se pudieron recalcular los avisos', e))
    }, 1500)
    return () => clearTimeout(t)
  }, [loaded, user, prefsKey, settings.notificationsVersion, update])

  const updateNotificationPrefs = useCallback(
    (patch) => update((prev) => ({ notifications: { ...getNotificationPrefs(prev), ...patch } })),
    [update],
  )

  return (
    <SettingsContext.Provider
      value={{
        settings,
        loaded,
        update,
        modules,
        enabledModules,
        getModule,
        toggleModule,
        moveModule,
        notificationPrefs,
        updateNotificationPrefs,
      }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export const useSettings = () => useContext(SettingsContext)
