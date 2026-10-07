# PACO OS

**Mi centro digital personal.** Un "sistema operativo" web donde organizar todo lo del día a día —tareas, estudios, notas, archivos, proyectos, películas, juegos, compras, finanzas, viajes, rutinas…— y que crece con módulos nuevos.

- Funciona en **PC, móvil y tablet** desde cualquier navegador (y se puede instalar como app).
- **No depende de Claude**: es una web normal publicada en GitHub Pages, con tus datos en tu propio Supabase.
- Arquitectura **modular**: añadir un módulo es crear un archivo o, sin programar, usar el constructor de módulos de la propia app.

Tecnología: React · Vite · JavaScript · CSS · Lucide React · Supabase (Auth, base de datos y Storage) · GitHub Pages.

---

## Qué incluye

| Sección | Qué hace |
| --- | --- |
| **Inicio** | Saludo, captura rápida a cualquier módulo, tareas de hoy, próximos 14 días, elementos fijados, actividad reciente, archivos recientes y lanzador de módulos. |
| **Calendario** | Vista mensual unificada con todo lo que tiene fecha en cualquier módulo (tareas, exámenes, entregas, viajes…). |
| **Buscador global** | `Ctrl + K` (o `⌘ + K`): ir a cualquier módulo, crear elementos y buscar en todo tu contenido. |
| **Módulos** | Activa/desactiva módulos, cambia su orden en el menú y **crea módulos propios sin programar** (campos, estados, icono, color, vista). |
| **Notificaciones** | Avisos push en móvil y PC: tareas, exámenes, eventos del calendario y avisos personalizados. Campana 🔔 con recientes y próximos. Ver **[docs/NOTIFICACIONES.md](docs/NOTIFICACIONES.md)**. |
| **Ajustes** | Nombre, tema claro/oscuro/sistema, color de acento, notificaciones, exportar/importar copia de seguridad (JSON), cambiar contraseña. |

Módulos incluidos de serie:

- **Activos por defecto:** Tareas · Avisos · Estudios · Notas · Archivos
- **Disponibles para activar:** Proyectos (kanban) · Ideas · Rutinas (con rachas) · Películas y series · Juegos · Compras · Finanzas (balance mensual) · Viajes · Mi PC · Enlaces

Cada módulo de tipo colección tiene vista de **tarjetas, lista o tablero kanban**, búsqueda, filtros por estado, ordenación, fijado en inicio y acciones rápidas.

---

## Puesta en marcha (paso a paso)

### 1. Probar en tu ordenador

Necesitas [Node.js](https://nodejs.org) 20 o superior.

```bash
npm install
npm run dev
```

Abre la dirección que aparece (normalmente http://localhost:5173).
Sin configurar nada, PACO OS arranca en **modo local**: los datos se guardan solo en ese navegador. Sirve para probarla.

### 2. Crear tu Supabase (base de datos, login y archivos)

1. Crea una cuenta gratuita en [supabase.com](https://supabase.com) y un **proyecto nuevo**.
2. Ve a **SQL Editor → New query**, pega el contenido de [`supabase/schema.sql`](supabase/schema.sql) y pulsa **Run**.
   Esto crea las tablas, la seguridad (cada usuario solo ve sus datos) y el bucket privado de archivos `paco-files`.
3. Ve a **Project Settings → API Keys** y copia:
   - `Project URL`
   - la **Publishable key** (`sb_publishable_...`). También sirve la clave `anon` clásica.
4. En tu ordenador, copia `.env.example` como `.env.local` y pega esos valores:

   ```env
   VITE_SUPABASE_URL=https://tu-proyecto.supabase.co
   VITE_SUPABASE_ANON_KEY=sb_publishable_...
   ```

   `.env.local` está en `.gitignore`: **nunca se sube a Git**. La app lee estas variables
   solo en `src/lib/supabase.js` mediante `import.meta.env`. Si falta alguna, arranca en modo local.

5. Reinicia `npm run dev`. Ahora verás la pantalla de login: **crea tu cuenta**.

> **Recomendado (uso personal):** cuando ya tengas tu cuenta creada, en Supabase ve a
> **Authentication → Sign In / Providers → Email** y desactiva **"Allow new users to sign up"**.
> Así nadie más podrá registrarse en tu PACO OS.

> La Publishable key (o `anon`) es pública por diseño: acaba dentro del JavaScript que descarga el navegador.
> La seguridad la garantizan las políticas RLS del `schema.sql` (cada usuario solo puede leer y escribir sus propias filas y su carpeta de Storage).
> **Nunca** pongas la Secret key / `service_role` en la app ni en los secretos de la web.

> Si actualizas PACO OS y cambia `supabase/schema.sql`, vuelve a ejecutarlo entero: es idempotente y no borra datos.

### 3. Publicar en GitHub Pages (para usarla desde cualquier dispositivo)

1. Sube este proyecto a un repositorio de GitHub (rama `main`).
2. En el repositorio: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. En **Settings → Secrets and variables → Actions → New repository secret**, crea:
   - `VITE_SUPABASE_ANON_KEY` → la **Publishable key** (`sb_publishable_...`). **Nunca** la Secret key (`sb_secret_...`).
   - `VITE_SUPABASE_URL` (opcional: si no existe se usa la URL del proyecto configurada en el workflow)

   El workflow comprueba la clave antes de compilar (sin mostrarla) y **detiene el despliegue** si es una clave secreta o `service_role`.
4. Cada `push` a `main` publica automáticamente la web (también puedes lanzarlo a mano en **Actions → Deploy a GitHub Pages → Run workflow**).
5. Tu PACO OS quedará en: `https://<tu-usuario>.github.io/<nombre-del-repo>/`
6. En Supabase, ve a **Authentication → URL Configuration**:
   - **Site URL:** `https://<tu-usuario>.github.io/<nombre-del-repo>/`
   - **Redirect URLs:** añade `https://<tu-usuario>.github.io/<nombre-del-repo>/**` y, para desarrollo, `http://localhost:5173/**`

   Así funcionan los correos de confirmación, el enlace mágico y la recuperación de contraseña (al abrir ese enlace, PACO OS te pide la nueva contraseña). Los enlaces deben abrirse en el mismo navegador desde el que se pidieron.

### 4. Instalar como app

- **Móvil:** abre la web → Safari: botón compartir → *Añadir a pantalla de inicio* · Chrome: menú ⋮ → *Instalar app*.
- **PC:** en Chrome/Edge, icono de instalar en la barra de direcciones.
- En iPhone/iPad las notificaciones solo funcionan con la app instalada así (iOS 16.4 o superior).

### 5. Notificaciones push (opcional, gratis)

Necesitan unos pasos únicos en Supabase (tablas, Edge Function y tarea programada) y la variable `VITE_VAPID_PUBLIC_KEY` en GitHub.
Guía paso a paso: **[docs/NOTIFICACIONES.md](docs/NOTIFICACIONES.md)**. Sin ellos, PACO OS funciona igual y los avisos se ven en la campana.

---

## Estructura del proyecto

```
paco-os/
├─ .github/workflows/deploy.yml   # Publicación automática en GitHub Pages
├─ supabase/schema.sql            # Tablas, seguridad RLS y bucket de archivos
├─ supabase/cron.sql              # Envío automático de notificaciones (Supabase Cron)
├─ supabase/functions/            # Edge Function send-notifications (Web Push)
├─ docs/MODULOS.md                # Cómo crear módulos nuevos
├─ docs/NOTIFICACIONES.md         # Cómo activar y ampliar las notificaciones
├─ scripts/test-webpush.mjs       # Prueba del cifrado Web Push (npm run test:push)
├─ public/                        # Iconos, manifest y service worker (sw.js)
└─ src/
   ├─ main.jsx · App.jsx          # Arranque y rutas (HashRouter)
   ├─ lib/
   │  ├─ api/                     # Capa de datos: supabaseBackend y localBackend (misma interfaz)
   │  ├─ supabase.js              # Cliente Supabase
   │  ├─ notifications/           # Reglas, sincronización y push de los avisos
   │  ├─ items.js · utils.js · icons.js
   ├─ context/                    # Sesión, ajustes/módulos activos, avisos y confirmaciones
   ├─ hooks/useItems.js           # CRUD genérico con actualizaciones optimistas
   ├─ modules/
   │  ├─ registry.js              # Registro automático de módulos
   │  ├─ definitions/             # ← UN ARCHIVO POR MÓDULO
   │  └─ views/                   # Vistas: genérica (CollectionView), Tareas, Notas, Archivos
   ├─ components/                 # Layout, modal, formularios, buscador, constructor de módulos…
   ├─ pages/                      # Inicio, Calendario, Módulos, Ajustes, Login
   └─ styles/global.css           # Tema claro/oscuro y diseño responsive
```

### Cómo está pensada la modularidad

- **Una sola tabla genérica (`items`)** guarda los elementos de todos los módulos. Cada fila lleva el id de su módulo, columnas comunes (`title`, `body`, `status`, `due_date`, `tags`, `pinned`) y un campo `data` (JSON) para lo específico. Resultado: **añadir un módulo nunca requiere tocar la base de datos.**
- **Registro automático**: cualquier archivo en `src/modules/definitions/` aparece solo en el menú, el buscador, el calendario y la página de módulos.
- **Vista genérica**: un módulo solo describe sus campos; formulario, tarjetas, lista, kanban, filtros y búsqueda se generan solos. Si un módulo necesita algo especial, puede aportar su propio componente (como Tareas, Notas o Archivos).
- **Capa de datos aislada** (`src/lib/api`): los módulos nunca hablan con Supabase directamente, así que cambiar o ampliar el backend no rompe nada.

Guía completa: **[docs/MODULOS.md](docs/MODULOS.md)**.

---

## Comandos

| Comando | Para qué |
| --- | --- |
| `npm run dev` | Servidor de desarrollo |
| `npm run build` | Genera la versión de producción en `dist/` |
| `npm run preview` | Sirve `dist/` para probarla |
| `npm run test:push` | Comprueba el cifrado Web Push de la Edge Function |
| `npx web-push generate-vapid-keys` | Genera las claves VAPID para las notificaciones |
