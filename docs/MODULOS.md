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
| `time` | Hora (HH:MM) |
| `datetime` | Fecha y hora |
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
| `notifications` | Avisos push del módulo (ver abajo) |
| `recurrence` | Elementos que se repiten (ver abajo) |

### Notificaciones de un módulo

Todo módulo con `due_date` y `showInCalendar: true` recibe **automáticamente** un aviso de tipo «evento» (09:00 del día, configurable en Ajustes). Para personalizarlo, declara `notifications`:

```js
notifications: {
  kind: 'exam',                                  // task | exam | event | custom | system
  time: (prefs, item) => prefs.examTime,         // hora local del aviso
  daysBefore: (prefs, item) => prefs.examDaysBefore,
  active: (item) => item.status !== 'aprobada',  // sin aviso si devuelve false
  message: (item, { days }) => ({ title: `Examen: ${item.title}`, body: days === 1 ? 'Es mañana' : '' }),
},
```

Cada elemento puede cambiarlo desde su formulario (campo **Recordatorio**). La sincronización con Supabase es automática. Más detalles en [NOTIFICACIONES.md](NOTIFICACIONES.md).

### Módulos con interfaz propia

Para algo totalmente distinto (un reproductor, un panel de automatizaciones, gráficos…), crea un componente en `src/modules/views/` y enlázalo con `component`. Dentro puedes usar:

- `useItems(module.id)` → `{ items, loading, create, update, remove }` (datos guardados en Supabase).
- `api` de `src/lib/api` → acceso a items, archivos y ajustes.
- `useUI()` → `toast()`, `confirm()`, `notifyError()`.
- Componentes de `src/components/` (`ModuleHeader`, `ItemEditor`, `Modal`, `EmptyState`…).

Mira `TasksView.jsx`, `NotesView.jsx` y `FilesView.jsx` como ejemplos.

### ¿Y si un módulo necesita su propia tabla?

Casi nunca hace falta (el campo `data` JSON admite cualquier estructura), pero si lo necesitas: añade la tabla con su política RLS en `supabase/schema.sql`, añade los métodos a **ambos** backends en `src/lib/api/` y úsalos desde tu componente.

### Elementos que se repiten

Añade un campo `repeat` y declara `recurrence` con el estado de «hecho» y el de «pendiente»:

```js
import { REPEAT_OPTIONS } from '../../lib/smart/recurrence'

recurrence: { doneStatus: 'hecha', openStatus: 'pendiente' },
fields: [
  // ...
  { key: 'repeat', label: 'Repetir', type: 'select', emptyLabel: 'No se repite', options: REPEAT_OPTIONS },
],
```

Al pasar un elemento a `doneStatus`, la capa de datos crea automáticamente el siguiente (cada día, entre semana, cada semana, cada 2 semanas, cada mes o cada año) con su aviso. El completado se queda como historial y no se duplica si se desmarca y se vuelve a marcar.

### Captura inteligente

Si el módulo tiene `due_date`, la captura rápida del Inicio entiende lenguaje natural («mañana a las 17:30», «el viernes», «cada lunes», «!alta») y rellena `due_date`, `repeat`, `priority` y `hora` cuando el módulo tiene esos campos. Intérprete: `src/lib/smart/parseQuick.js` (pruebas: `npm run test:smart`).
