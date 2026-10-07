// Permisos de PACO AI: qué puede hacer sola la IA y qué necesita tu confirmación.
// Se guardan en los ajustes del usuario (settings.ai.permissions) y se aplican
// en el navegador ANTES de ejecutar cualquier herramienta, sin depender del modelo.
//
//   auto -> se ejecuta sin preguntar
//   ask  -> la app muestra la acción y espera a que la apruebes o rechaces
//   off  -> bloqueado: la IA recibe "acción no permitida"

export const PERMISSION_KINDS = [
  { kind: 'read', label: 'Consultar tus datos', hint: 'Buscar elementos, ver la agenda y los nombres de tus archivos.', options: ['auto', 'off'] },
  { kind: 'create', label: 'Crear elementos', hint: 'Tareas, avisos, notas…', options: ['ask', 'auto', 'off'] },
  { kind: 'update', label: 'Editar elementos', hint: 'Cambiar fechas, completar tareas, fijar…', options: ['ask', 'auto', 'off'] },
  // Borrar SIEMPRE requiere confirmación: no existe la opción "auto".
  { kind: 'delete', label: 'Eliminar elementos', hint: 'Siempre pide confirmación.', options: ['ask', 'off'] },
]

export const PERMISSION_LABELS = { auto: 'Sin preguntar', ask: 'Preguntar', off: 'No permitir' }

export const DEFAULT_AI_PERMISSIONS = { read: 'auto', create: 'ask', update: 'ask', delete: 'ask' }

// Permisos efectivos: valores desconocidos o no permitidos vuelven al valor seguro por defecto.
export function getAiPermissions(settings) {
  const saved = settings?.ai?.permissions || {}
  const out = {}
  for (const { kind, options } of PERMISSION_KINDS) {
    out[kind] = options.includes(saved[kind]) ? saved[kind] : DEFAULT_AI_PERMISSIONS[kind]
  }
  return out
}

export function policyFor(permissions, kind) {
  if (!kind) return 'off'
  const p = permissions[kind] ?? DEFAULT_AI_PERMISSIONS[kind] ?? 'off'
  if (kind === 'delete' && p === 'auto') return 'ask'
  return p
}
