# Crear módulos en PACO OS

Hay dos formas de añadir módulos.

## Opción A — Sin programar (desde la app)

**Módulos → Crear módulo.** Eliges nombre, icono, color, vista (tarjetas, lista o kanban), estados y campos extra (texto, número, dinero, fecha, lista de opciones, estrellas, progreso, enlace, sí/no). Se guarda en tus ajustes y se sincroniza en todos tus dispositivos.

Ideal para: libros, recetas, gimnasio, mascotas, coches, colecciones, regalos…

## Opción B — Con código (un archivo)

Crea `src/modules/definitions/mi-modulo.js`. Se registra **automáticamente**: no hay que tocar rutas, menú ni base de datos.

```js
import { BookOpen } from 'lucide-react'

export default {
  id: 'libros',                 // único, en minúsculas (va en la URL: #/m/libros)
  name: 'Libros',
  description: 'Lo que leo y quiero leer.',
  icon: BookOpen,               // cualquier icono de https://lucide.dev
  color: '#f59e0b',
  category: 'Ocio',             // agrupa en la página de Módulos
  defaultEnabled: false,        // true = activo para usuarios nuevos
  itemName: 'libro',            // "Nuevo libro", "Editar libro"
  layout: 'cards',              // 'cards' | 'list' | 'board'
  showInCalendar: false,        // true = los elementos con due_date salen en el calendario

  fields: [
    { key: 'title', label: 'Título', type: 'text', required: true },
    {
      key: 'status', label: 'Estado', type: 'select', default: 'pendiente',
      options: [
        { value: 'pendiente', label: 'Pendiente', color: '#64748b' },
        { value: 'leyendo',   label: 'Leyendo',   color: '#3b82f6' },
        { value: 'leido',     label: 'Leído',     color: '#22c55e' },
      ],
    },
    { key: 'autor', label: 'Autor', type: 'text' },
    { key: 'paginas', label: 'Páginas', type: 'number', min: 0 },
    { key: 'puntuacion', label: 'Puntuación', type: 'rating' },
    { key: 'tags', label: 'Etiquetas', type: 'tags' },
    { key: 'body', label: 'Notas', type: 'textarea' },
  ],

  // Opcional: cifras resumen arriba del módulo
  summary: (items) => [
    { label: 'Leídos', value: items.filter((i) => i.status === 'leido').length },
  ],

  // Opcional: botones de acción rápida en cada elemento
  actions: [
    { label: 'Marcar leído', when: (i) => i.status !== 'leido', run: () => ({ status: 'leido' }) },
  ],
}
```

Si quieres que esté en una posición concreta del menú por defecto, añade su id a `DEFAULT_ORDER` en `src/modules/registry.js` (opcional).

### Campos

Claves **núcleo** (columnas propias, se pueden filtrar/ordenar en la base de datos):
`title`, `body`, `status`, `due_date`, `tags`. Cualquier otra clave se guarda automáticamente en `item.data`.

| `type` | Control |
| --- | --- |
| `text` | Texto corto |
| `textarea` | Texto largo |
| `number` | Número (`min`, `max`, `step`) |
| `money` | Importe en € |
| `date` | Fecha |
| `select` | Desplegable (`options: [{ value, label, color? }]`) |
| `rating` | 0–5 estrellas |
| `progress` | Barra 0–100 % |
| `url` | Enlace |
| `checkbox` | Sí / No |
| `tags` | Etiquetas |

Propiedades extra de un campo: `required`, `placeholder`, `default` (valor o función), `readOnly`, `hideInMeta` (no mostrar en tarjetas).

### Otras opciones del módulo

| Opción | Para qué |
| --- | --- |
| `subtitle(item)` | Texto secundario bajo el título |
| `calendarLabel(item)` | Texto en el calendario (p. ej. `Examen: …`) |
| `openUrlField` | Campo con URL que se abre con un botón |
| `sortDefault` | `'recent'`, `'title'`, `'due_date'` o `'rating'` |
| `component` | Componente React propio en lugar de la vista genérica (recibe `{ module }`) |
| `usesItems: false` | El módulo no usa la tabla `items` (como Archivos) |

### Módulos con interfaz propia

Para algo totalmente distinto (un reproductor, un panel de automatizaciones, gráficos…), crea un componente en `src/modules/views/` y enlázalo con `component`. Dentro puedes usar:

- `useItems(module.id)` → `{ items, loading, create, update, remove }` (datos guardados en Supabase).
- `api` de `src/lib/api` → acceso a items, archivos y ajustes.
- `useUI()` → `toast()`, `confirm()`, `notifyError()`.
- Componentes de `src/components/` (`ModuleHeader`, `ItemEditor`, `Modal`, `EmptyState`…).

Mira `TasksView.jsx`, `NotesView.jsx` y `FilesView.jsx` como ejemplos.

### ¿Y si un módulo necesita su propia tabla?

Casi nunca hace falta (el campo `data` JSON admite cualquier estructura), pero si lo necesitas: añade la tabla con su política RLS en `supabase/schema.sql`, añade los métodos a **ambos** backends en `src/lib/api/` y úsalos desde tu componente.
