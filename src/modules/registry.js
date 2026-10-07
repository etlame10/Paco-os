// =====================================================================
// REGISTRO DE MÓDULOS
// Cualquier archivo dentro de ./definitions/ se registra AUTOMÁTICAMENTE.
// Para añadir un módulo nuevo basta con crear ./definitions/mi-modulo.js
// (ver docs/MODULOS.md). No hay que tocar rutas, menús ni base de datos.
// =====================================================================
import { getIcon } from '../lib/icons'

const files = import.meta.glob('./definitions/*.js', { eager: true })

// Orden por defecto en el menú (los no listados van al final, por nombre).
const DEFAULT_ORDER = [
  'tareas', 'avisos', 'estudios', 'notas', 'archivos', 'proyectos', 'ideas', 'rutinas',
  'peliculas', 'juegos', 'compras', 'finanzas', 'viajes', 'pc', 'enlaces',
]

export const STATIC_MODULES = Object.values(files)
  .map((m) => m.default)
  .filter((m) => m && m.id)
  .sort((a, b) => {
    const ia = DEFAULT_ORDER.indexOf(a.id)
    const ib = DEFAULT_ORDER.indexOf(b.id)
    if (ia === -1 && ib === -1) return a.name.localeCompare(b.name)
    if (ia === -1) return 1
    if (ib === -1) return -1
    return ia - ib
  })

export const DEFAULT_ENABLED = STATIC_MODULES.filter((m) => m.defaultEnabled).map((m) => m.id)

// Los módulos personalizados se crean desde la propia app (Módulos > Crear módulo)
// y se guardan en los ajustes del usuario como JSON. Aquí se convierten en
// módulos de tipo "colección" igual que los definidos en código.
export function buildCustomModule(def) {
  const statusOptions = (def.statuses || []).filter((s) => s.label?.trim())
  const fields = [
    { key: 'title', label: def.titleLabel || 'Título', type: 'text', required: true },
  ]
  if (statusOptions.length) {
    fields.push({
      key: 'status',
      label: 'Estado',
      type: 'select',
      default: statusOptions[0].value,
      options: statusOptions,
    })
  }
  for (const f of def.fields || []) fields.push(f)
  if (def.withDate) fields.push({ key: 'due_date', label: def.dateLabel || 'Fecha', type: 'date' })
  fields.push({ key: 'tags', label: 'Etiquetas', type: 'tags' })
  fields.push({ key: 'body', label: 'Notas', type: 'textarea' })

  return {
    id: def.id,
    name: def.name,
    description: def.description || 'Módulo personalizado',
    icon: getIcon(def.icon),
    iconName: def.icon,
    color: def.color || '#7c5cff',
    category: 'Personalizados',
    itemName: def.itemName || 'elemento',
    layout: def.layout || 'cards',
    showInCalendar: Boolean(def.withDate),
    fields,
    custom: true,
    raw: def,
  }
}
