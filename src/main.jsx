import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/global.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Service worker: necesario para instalar PACO OS como app y recibir notificaciones push.
// Solo en producción (en desarrollo Vite recarga la página y no hace falta).
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch((e) => console.warn('[PACO OS] Service worker no registrado', e))
  })
}
