import { useEffect, useState } from 'react'
import { isStandalone } from '../lib/notifications/push'

// Chrome/Edge/Android lanzan "beforeinstallprompt": se guarda para mostrar un botón "Instalar".
let deferred = null
const listeners = new Set()
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferred = e
    listeners.forEach((l) => l(e))
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    listeners.forEach((l) => l(null))
  })
}

export function useInstallPrompt() {
  const [prompt, setPrompt] = useState(deferred)
  useEffect(() => {
    listeners.add(setPrompt)
    return () => listeners.delete(setPrompt)
  }, [])

  const install = async () => {
    if (!prompt) return false
    prompt.prompt()
    const { outcome } = await prompt.userChoice
    deferred = null
    setPrompt(null)
    return outcome === 'accepted'
  }

  return { canInstall: Boolean(prompt), install, installed: isStandalone() }
}
