// Preferencias de notificaciones (se guardan en user_settings.settings.notifications).
// La Edge Function "send-notifications" usa los mismos valores por defecto.

export const NOTIFICATION_KINDS = [
  { id: 'task', label: 'Tareas', description: 'Recordatorio el día límite de cada tarea pendiente.' },
  { id: 'exam', label: 'Exámenes', description: 'Aviso antes de cada examen de Estudios.' },
  { id: 'event', label: 'Eventos del calendario', description: 'Entregas de proyectos, viajes y módulos con fecha.' },
  { id: 'custom', label: 'Avisos personalizados', description: 'Lo que programes en el módulo Avisos.' },
  { id: 'system', label: 'Avisos de PACO OS', description: 'Pruebas, novedades y avisos del propio sistema.' },
]

export const DEFAULT_NOTIFICATION_PREFS = {
  kinds: { task: true, exam: true, event: true, custom: true, system: true },
  taskTime: '09:00', // tareas: a esta hora del día límite
  examTime: '18:00', // exámenes: a esta hora...
  examDaysBefore: 1, // ...este número de días antes
  eventTime: '09:00', // eventos: a esta hora del mismo día
  quietStart: '23:00', // horas de silencio: los avisos se retrasan hasta quietEnd
  quietEnd: '08:00',
  timezone: 'Europe/Madrid',
}

export function getNotificationPrefs(settings) {
  const p = settings?.notifications || {}
  return {
    ...DEFAULT_NOTIFICATION_PREFS,
    ...p,
    kinds: { ...DEFAULT_NOTIFICATION_PREFS.kinds, ...(p.kinds || {}) },
  }
}
