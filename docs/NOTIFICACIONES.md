# Notificaciones push en PACO OS

PACO OS envía avisos al móvil y al PC con el estándar **Web Push**, usando solo la infraestructura gratuita que ya tienes: GitHub Pages y Supabase (plan gratuito). No hace falta ningún servicio de pago ni tarjeta.

## Cómo funciona

```
 Móvil / PC (PACO OS instalada)            Supabase (plan gratuito)
 ┌────────────────────────┐  suscripción   ┌──────────────────────────────┐
 │ Service worker (sw.js) │ ─────────────► │ push_subscriptions (RLS)     │
 │  · muestra el aviso    │                │ notifications (RLS)          │
 │  · al tocarlo abre el  │                │   kind, remind_at, status... │
 │    elemento en la app  │                │            ▲                 │
 └──────────▲─────────────┘                │ Supabase Cron (cada 5 min)   │
            │ Web Push cifrado             │   └► Edge Function           │
 ┌──────────┴─────────────┐                │      send-notifications      │
 │ Google / Apple /       │ ◄───────────── │      (clave VAPID privada    │
 │ Mozilla (gratuitos)    │                │       como secreto)          │
 └────────────────────────┘                └──────────────────────────────┘
```

1. Cuando guardas una tarea, examen, aviso o cualquier elemento con fecha, PACO OS programa su aviso en la tabla `notifications` (lo hace la capa de datos automáticamente).
2. Cada 5 minutos, **Supabase Cron** llama a la Edge Function **`send-notifications`**, que envía los avisos cuya hora ha llegado a todos tus dispositivos activados.
3. Los avisos también quedan en la **campana** 🔔 de PACO OS (recientes y próximos).

### Qué avisa y cuándo (valores por defecto, cambiables en Ajustes → Notificaciones)

| Tipo | Origen | Aviso por defecto |
|---|---|---|
| Tareas | módulo Tareas (pendientes con fecha límite) | 09:00 del día límite |
| Exámenes | módulo Estudios («Próximo examen») | 18:00 del día anterior |
| Eventos | cualquier módulo con fecha que aparezca en el calendario (Proyectos, Viajes, módulos personalizados…) | 09:00 del mismo día |
| Avisos personalizados | módulo **Avisos** (fecha + hora) | a la hora indicada |
| Sistema | avisos de prueba y del propio PACO OS | al momento |

- **Horas de silencio:** 23:00–08:00. Lo que caiga en esa franja se entrega al terminar.
- **Zona horaria:** Europe/Madrid (tiene en cuenta los cambios de hora).
- Cada elemento tiene en su formulario un campo **Recordatorio**: *por defecto*, *fecha y hora concretas* o *sin aviso*.
- Al completar una tarea, quitarle la fecha o borrarla, su aviso pendiente desaparece.
- En **modo local** (sin Supabase) no hay push: los avisos se muestran solo mientras PACO OS está abierto.

## Requisitos de cada dispositivo

| Dispositivo | Requisitos |
|---|---|
| **Android** | Chrome, Edge, Firefox o Samsung Internet. Recomendado instalar la app (menú ⋮ → *Instalar app*). |
| **iPhone / iPad** | **iOS/iPadOS 16.4 o superior** y PACO OS **añadido a la pantalla de inicio** desde Safari (Compartir → *Añadir a pantalla de inicio*). Abre PACO OS desde ese icono para activar los avisos. En una pestaña normal de Safari no funcionan. |
| **PC / Mac** | Chrome, Edge, Firefox o Safari actualizados (instalar la app es opcional). |

El permiso siempre se pide al pulsar **Activar notificaciones en este dispositivo** (Ajustes → Notificaciones). Cada dispositivo se activa por separado.

---

## Activación (una sola vez, ~10 minutos)

> Nada de esto borra ni modifica tus datos. Los SQL solo **añaden** tablas y una tarea programada.
> Las claves privadas solo se guardan en **Supabase**. Nunca en GitHub ni en la web.

### Paso 1 · Actualizar la base de datos
1. Supabase → **SQL Editor** → *New query*.
2. Pega el contenido **completo** de [`supabase/schema.sql`](../supabase/schema.sql) y pulsa **Run**.
   Crea las tablas `push_subscriptions` y `notifications` con seguridad RLS. Es idempotente.

### Paso 2 · Generar las claves VAPID (en tu PC)
En una terminal (con Node.js instalado), dentro de la carpeta del proyecto o en cualquier otra:

```bash
npx web-push generate-vapid-keys
```

Obtendrás una **Public Key** (87 caracteres, empieza por `B`) y una **Private Key** (43 caracteres).
Guarda la privada en un lugar seguro: si se pierde, basta con generar un par nuevo y volver a activar los dispositivos.

### Paso 3 · Guardar los secretos de la Edge Function
Supabase → **Edge Functions** → **Secrets** → añade:

| Nombre | Valor |
|---|---|
| `VAPID_PUBLIC_KEY` | la Public Key |
| `VAPID_PRIVATE_KEY` | la Private Key |
| `VAPID_SUBJECT` | `mailto:tu-correo@ejemplo.com` (contacto que piden Apple/Google) |

(`CRON_SECRET` se añade en el paso 6.)

### Paso 4 · Publicar la Edge Function desde el panel
1. Supabase → **Edge Functions** → **Deploy a new function** → **Via Editor**.
2. Nombre: **`send-notifications`** (exactamente así).
3. Borra el código de ejemplo y pega el contenido completo de [`supabase/functions/send-notifications/index.ts`](../supabase/functions/send-notifications/index.ts).
4. Pulsa **Deploy function**.
5. En la función → **Details / Settings**: **desactiva «Verify JWT» / «Enforce JWT verification»** y guarda.
   La función hace su propia comprobación: el token de Cron para el envío automático, o tu sesión de PACO OS para el aviso de prueba.

### Paso 5 · Programar el envío automático
1. Supabase → **SQL Editor** → *New query*.
2. Pega el contenido de [`supabase/cron.sql`](../supabase/cron.sql) y pulsa **Run**.
3. El resultado muestra una columna **`copia_este_valor_en_CRON_SECRET`** con un token largo. Cópialo.

### Paso 6 · Guardar el token de Cron
Supabase → **Edge Functions** → **Secrets** → añade `CRON_SECRET` con el valor copiado.

### Paso 7 · Clave pública en GitHub y nuevo despliegue
1. GitHub → repositorio → **Settings → Secrets and variables → Actions → pestaña Variables** → **New repository variable**:
   - Nombre: `VITE_VAPID_PUBLIC_KEY`
   - Valor: la **Public Key** (¡no la privada!; el despliegue se detiene si detecta la privada).
2. **Actions → Deploy a GitHub Pages → Run workflow** (rama `main`).

### Paso 8 · Activar tus dispositivos y probar
1. Abre PACO OS (en iPhone, desde el icono de la pantalla de inicio).
2. **Ajustes → Notificaciones → Activar notificaciones en este dispositivo** → *Permitir*.
3. Pulsa **Enviar aviso de prueba**: debe llegarte «¡Las notificaciones funcionan! 🎉».
4. Repite en cada dispositivo (móvil, tablet, PC).

---

## Comprobaciones y mantenimiento

**Ver si Cron se está ejecutando** (SQL Editor):
```sql
select status, return_message, start_time
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'paco-send-notifications')
order by start_time desc limit 20;
```

**Ver los avisos programados y su estado:**
```sql
select kind, title, remind_at, status, attempts, last_error
from public.notifications order by remind_at desc limit 50;
```

**Logs de la función:** Supabase → Edge Functions → `send-notifications` → *Logs*.

**Pausar el envío automático** (no borra nada): `select cron.unschedule('paco-send-notifications');`
Para reactivarlo, vuelve a ejecutar `supabase/cron.sql`.

**Si actualizas el código de la función:** pega de nuevo `index.ts` en el editor de la función y vuelve a publicar.

## Costes y límites (plan gratuito de Supabase)

| Recurso | Uso de PACO OS | Límite gratuito |
|---|---|---|
| Edge Functions | ~9.000 llamadas/mes (cada 5 min) + pruebas | 500.000/mes |
| Base de datos | unos pocos KB de avisos | 500 MB |
| Supabase Cron (pg_cron) | 1 tarea | incluido |
| Servicios de push (Google/Apple/Mozilla) | — | gratuitos |

**Coste: 0 €.**

### ⚠️ Pausa por inactividad
Supabase **pausa los proyectos gratuitos tras unos 7 días sin actividad**. Las tareas de Supabase Cron se ejecutan *dentro* de la base de datos y **no cuentan como actividad**: no evitan la pausa y, mientras el proyecto está pausado, **no se envía ningún aviso**. Con un uso normal de PACO OS (abrirlo de vez en cuando) no ocurre. Si se pausara:
- Supabase avisa por correo antes de pausar.
- Los datos **no se pierden**. Se reactiva desde el panel (*Restore project*) durante 90 días.
- Al reactivarse, los avisos con más de 24 h de retraso se descartan (no te llegará una avalancha de avisos antiguos). Los demás se envían con normalidad.

## Seguridad
- Clave VAPID **privada** y `CRON_SECRET`: solo en los secretos de la Edge Function (y el token, también cifrado en Supabase Vault).
- La función usa internamente la clave de servicio que Supabase le inyecta. Nunca sale de Supabase ni aparece en la web o en GitHub.
- Tablas con **RLS**: cada usuario solo ve y modifica sus avisos y sus dispositivos.
- El aviso de prueba solo puede enviarse a los dispositivos de quien lo solicita.

## Para desarrolladores
- Reglas de avisos: `src/lib/notifications/rules.js`. Un módulo declara `notifications` en su definición (ver [MODULOS.md](MODULOS.md)). Los módulos con fecha que salen en el calendario reciben avisos de tipo «evento» automáticamente.
- Sincronización automática: `src/lib/notifications/sync.js`, llamada desde `src/lib/api/index.js`.
- Navegador: `src/lib/notifications/push.js` y `public/sw.js`.
- Envío: `supabase/functions/send-notifications/index.ts` (Web Push con WebCrypto, sin dependencias).
- Prueba del cifrado contra librerías de referencia: `npm run test:push`.
