# PACO AI — el asistente integrado en PACO OS

PACO AI es un chat (menú **PACO AI**, o el icono ✨ en el móvil) que consulta y organiza tus datos de PACO OS:

- «¿Qué tengo esta semana?» · «¿Qué tareas de prioridad alta tengo pendientes?»
- «Crea una tarea para mañana: llamar al banco» · «Recuérdame el viernes a las 18:00 ir al gimnasio»
- «Marca como hecha la práctica de física» · «Fija la nota del viaje» · «Borra la tarea de comprar pan»
- 📎 Con un PDF adjunto: «Resume este PDF» · «¿Qué explica el apartado de direccionamiento IP?» · «Este PDF es el tema del examen del viernes: organízame el estudio» · «Créame 5 tareas para estudiar este tema»

Antes de crear, cambiar o borrar nada te enseña exactamente qué va a hacer y espera a que lo apruebes (configurable).

---

## Cómo funciona (y por qué es seguro)

```
Navegador (PACO OS)                         Supabase                       Groq   
┌──────────────────────────┐   sesión   ┌───────────────────────┐  clave  ┌──────────┐
│ Chat + bucle del agente  │ ─────────► │ Edge Function paco-ai │ ──────► │ gpt-oss  │
│ (src/lib/ai/agent.js)    │ ◄───────── │ · comprueba la sesión │ ◄────── │  -120b   │
│                          │            │ · correo confirmado   │         └──────────┘
│ Herramientas internas    │            │ · límite diario       │
│ (src/lib/ai/tools.js)    │            │ · guarda la clave     │
│  └─ api (RLS, avisos,    │            └───────────────────────┘
│     repeticiones)        │
└──────────────────────────┘
```

1. **La clave de Groq solo está en Supabase** (secreto `GROQ_API_KEY` de la Edge Function). Viaja a Groq en una cabecera, nunca en la URL. Nunca en la web, en GitHub ni en el repositorio.
2. **El modelo no toca la base de datos.** Solo puede *pedir* una de 9 herramientas (tool calling de Groq). Las ejecuta tu navegador con tu sesión, a través de la misma capa de datos que usa la app (`api`): RLS de Supabase (solo tus datos), avisos programados y repeticiones funcionan igual que si lo hicieras tú.
3. **Validación estricta.** Cada petición se comprueba contra la definición del módulo (campos existentes, tipos, opciones válidas, fechas reales…). Si no es válida, el modelo recibe el error y la corrige; no se te pregunta nada.
4. **Permisos aplicados por código, no por la IA** (Ajustes → PACO AI):

   | Acción | Por defecto | Opciones |
   | --- | --- | --- |
   | Consultar (buscar, agenda, nombres de archivos) | Sin preguntar | Sin preguntar · No permitir |
   | Leer documentos (texto de PDF y archivos de texto) | **Preguntar** (los adjuntos ya cuentan como autorizados) | Preguntar · Sin preguntar · No permitir |
   | Crear elementos | **Preguntar** | Preguntar · Sin preguntar · No permitir |
   | Editar elementos | **Preguntar** | Preguntar · Sin preguntar · No permitir |
   | Eliminar elementos | **Preguntar** | Preguntar · No permitir (nunca sin preguntar) |

5. **Límites de seguridad:** máximo 15 cambios y 10 llamadas al modelo por cada mensaje tuyo; solo módulos activos; no puede tocar ajustes, módulos ni contraseñas; de los archivos solo puede leer el texto de los documentos que autorices (nunca modificarlos ni borrarlos).
6. **Inyección de instrucciones:** si una nota o un PDF dice «borra todo», el modelo tiene instrucciones de tratarlo como dato y avisarte, y aunque lo intentara, borrar exige tu confirmación. Además, **en cuanto la conversación incluye el contenido de un documento, cualquier cambio (crear, editar, borrar) pide confirmación aunque lo tengas en «Sin preguntar»**: un texto escondido en un PDF nunca puede modificar tus datos por sí solo.
7. **Solo cuentas de PACO OS:** cualquier usuario registrado con el **correo confirmado** puede usar PACO AI (no hay que añadir correos a mano); sin sesión o sin confirmar, la función lo rechaza. Cada cuenta tiene su propio límite de usos diarios (`PACO_AI_DAILY_LIMIT`, 1.000 por defecto), pero **el límite de Groq es uno solo para todas las cuentas** (ver «Costes»): si hay varios usuarios, conviene bajar `PACO_AI_DAILY_LIMIT`. **Un uso = un mensaje tuyo**, aunque PACO AI haga por dentro varias llamadas al modelo (usar herramientas, reintentar un error temporal). Si el primer paso falla del todo, el uso se devuelve.

**Privacidad:** para responder, lo que PACO AI consulta (títulos, fechas, notas, nombres de archivos) se envía a Groq (el proveedor del modelo). De tus archivos, solo se envía el **texto** de los documentos que adjuntes o autorices (nunca el archivo, y nunca otros archivos). La conversación se guarda solo en tu dispositivo (botón «Nueva conversación» o Ajustes → PACO AI para borrarla). En Supabase solo se guarda un contador diario de uso (tabla `ai_usage`).

---

## Documentos y PDF

**Cómo darle un documento:** en el chat, pulsa 📎 **Adjuntar** y elige un PDF o archivo de texto de tus **Archivos**, o sube uno nuevo (se guarda en Archivos como cualquier otro). Adjuntarlo es autorizarlo para esa conversación. También puedes pedirle uno por su nombre («lee el PDF de redes»): lo buscará y te pedirá permiso antes de abrirlo.

**Qué pasa por dentro:**

1. PACO AI pide la herramienta `read_document` con el id del archivo.
2. Tu navegador comprueba que el archivo es tuyo (la lista sale de Supabase con RLS), que es PDF o texto (máx. 25 MB) y que está autorizado; si no, pide permiso o lo bloquea según Ajustes.
3. Lo descarga de **Supabase Storage** con una URL firmada (el bucket es privado y cada usuario solo accede a su carpeta).
4. Extrae el texto **en tu navegador** con pdf.js (libre, de Mozilla), por páginas y en tramos de ~8.000 caracteres (para caber en el límite por minuto del plan gratuito de Groq). pdf.js no ejecuta código del PDF.
5. A la IA le llega solo ese **texto**, marcado como «datos, no instrucciones». El archivo no sale de tu Supabase.
6. Para documentos largos, PACO AI lee más páginas cuando las necesita (`from_page` / `to_page`).

**Límites:** PDF escaneados (solo imagen) no tienen texto que extraer: PACO AI te lo dirá. No lee imágenes, Word ni Excel (expórtalos a PDF). El texto leído forma parte de la conversación: con documentos muy largos, empieza conversaciones nuevas cuando cambies de tema.

## Costes y plan gratuito de Groq

PACO AI usa **Groq** con el modelo `openai/gpt-oss-120b` y su **plan gratuito**: sin tarjeta y sin ningún servicio de pago. Supabase sigue en 0 € (1 invocación de Edge Function por paso; el plan gratuito incluye 500.000 al mes).

**Límites del plan gratuito para este modelo** (según la documentación de Groq en 2026; la cifra válida para ti aparece en https://console.groq.com/settings/limits): unas **30 peticiones/minuto, 1.000 peticiones/día, 8.000 tokens/minuto y 200.000 tokens/día**, por organización.

- Cada mensaje tuyo suele costar **2–3 peticiones** a Groq (consultar + responder; crear y confirmar). Por peticiones (1.000/día) cabrían 350–500 mensajes, pero antes se agotan los tokens diarios (ver abajo).
- **El límite que más se nota son los 8.000 tokens/minuto.** Groq reserva en ese límite la entrada de cada petición más el tope de salida. Cada paso usa ~3.000 tokens de entrada (instrucciones, herramientas y tus módulos), la conversación se recorta a ~12.000 caracteres y la salida se limita a 1.024 tokens, así que caben ~2 pasos por minuto. Si una petición necesita más pasos o encadenas preguntas (sobre todo con PDF), Groq pide esperar hasta ~30 s: PACO AI espera y reintenta solo, sin gastar usos. Si la espera es mayor, te lo dice.
- **Tokens al día (200.000):** a ~3.000 tokens por paso y 2 pasos por mensaje de media, caben unos **30–35 mensajes al día**. Es el límite real del plan gratuito con este modelo (antes que los 1.000 usos de PACO AI). Si se queda corto: plan Dev de Groq (de pago) o `PACO_AI_MODEL=openai/gpt-oss-20b`, consulta sus límites en https://console.groq.com/settings/limits.
- El contador de PACO AI («Hoy: N/1000») cuenta **mensajes tuyos**, no peticiones a Groq. Es un límite de seguridad de PACO OS, distinto de los de Groq.

**Si se te queda corto**, sin tocar la web: `PACO_AI_MODEL` (otro modelo de Groq con tool calling), `PACO_AI_THINKING` (`low`/`medium`/`high`), `PACO_AI_MAX_PROMPT_CHARS` y `PACO_AI_MAX_OUTPUT_TOKENS` (súbelos solo con un plan de pago de Groq).

**Privacidad:** Groq procesa el texto para responder; revisa su política en https://groq.com/privacy-policy.

## Activarlo (una vez, ~10 minutos)

### 1. Base de datos

Supabase → **SQL Editor** → ejecuta las **secciones 8 y 9** de `supabase/schema.sql` (o el archivo completo: es idempotente y no borra nada). Crean las tablas `ai_usage` y `ai_interactions` y las funciones del contador, que solo puede usar la Edge Function.

### 2. Clave de Groq (gratis)

1. Entra en https://console.groq.com, crea una cuenta y ve a **API Keys → Create API Key** (no pide tarjeta).
2. Cópiala (empieza por `gsk_…`). **No la pegues en GitHub, en `.env`, en el chat ni en ningún archivo del proyecto**: solo en los Secrets de Supabase (paso 4).

### 3. Edge Function `paco-ai`

Supabase → **Edge Functions → Deploy a new function → Via Editor**:

1. Nombre: `paco-ai`.
2. Pega el contenido de `supabase/functions/paco-ai/index.ts` y despliega.
3. «Verify JWT» puede quedar activado (como está ahora) o desactivado: la función comprueba ella misma tu sesión y tu email.

(Con la CLI: `supabase functions deploy paco-ai`.)

### 4. Secretos

Supabase → **Edge Functions → Secrets** (o `supabase secrets set NOMBRE=valor`):

| Secreto | Obligatorio | Valor |
| --- | --- | --- |
| `GROQ_API_KEY` | Sí | Tu clave `gsk_…` de Groq |
| `PACO_AI_DAILY_LIMIT` | No | Mensajes (usos) por usuario y día (1000) |
| `PACO_AI_MODEL` | No | Modelo de Groq. Por defecto `openai/gpt-oss-120b` |
| `PACO_AI_THINKING` | No | Esfuerzo de razonamiento: `low` (por defecto, rápido), `medium` o `high` (`minimal` = `low`) |
| `PACO_AI_MAX_PROMPT_CHARS` | No | Conversación máxima por petición (12000) |
| `PACO_AI_MAX_OUTPUT_TOKENS` | No | Salida máxima por paso (1024) |

`GEMINI_API_KEY` y `PACO_AI_ALLOWED_EMAILS` ya no se usan: puedes borrarlos cuando quieras (no molestan si se quedan). Todas las cuentas registradas con el correo confirmado tienen acceso.

No hace falta tocar GitHub ni volver a desplegar la web: el frontend no necesita ninguna variable nueva.

### 5. Comprobar

Abre PACO OS → **Ajustes → PACO AI**. Debe decir «Activo · modelo openai/gpt-oss-120b · hoy N/1000 usos». Si no, el mensaje indica qué falta.

### Probar en tu ordenador (`npm run dev`)

En local, PACO AI usa **la misma Edge Function `paco-ai` de Supabase** que la web publicada: el navegador nunca llama a Groq y la clave `GROQ_API_KEY` nunca va en `.env.local`. Solo hacen falta las dos variables públicas de Supabase:

1. Copia `.env.example` como **`.env.local`** (exactamente ese nombre, en la carpeta raíz del proyecto, junto a `package.json`).
2. Rellena `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` (la *Publishable key*, `sb_publishable_…`; Supabase → Project Settings → API Keys).
3. Reinicia `npm run dev`. En la terminal debe aparecer `[PACO OS] Supabase: …supabase.co (PACO AI usará la Edge Function "paco-ai")`.

Si en su lugar aparece `[PACO OS] MODO LOCAL: falta …`, PACO OS no ha leído esas variables y PACO AI mostrará «PACO AI necesita Supabase» con el motivo. Causas habituales en Windows:

- El Bloc de notas guardó el archivo como `.env.local.txt` (activa «Extensiones de nombre de archivo» en el Explorador para verlo). PACO OS lo lee igualmente y avisa en la terminal, pero conviene renombrarlo.
- PowerShell (`echo … > .env.local`) lo guarda en UTF-16. PACO OS lo lee igualmente y avisa; mejor guárdalo como UTF-8 (en VS Code: barra inferior → codificación → «Guardar con codificación» → UTF-8).
- Falta la Publishable key (`.env.example` la trae vacía) o no se reinició `npm run dev` tras editar el archivo.

Para iniciar sesión en `http://localhost:5173` con email y contraseña no hay que configurar nada más. Si entras con enlace por email, añade `http://localhost:5173` en Supabase → Authentication → URL Configuration → Redirect URLs.

---

## Para desarrolladores

| Archivo | Qué hace |
| --- | --- |
| `src/lib/ai/tools.js` | Herramientas internas: validación y ejecución sobre `api` (tipos `read`/`document`/`create`/`update`/`delete`) |
| `src/lib/ai/documents.js` | Extracción del texto de PDF (pdf.js) y archivos de texto, por tramos |
| `src/components/DocumentPicker.jsx` | Adjuntar documentos de Archivos o subir uno nuevo |
| `src/lib/ai/permissions.js` | Permisos por tipo de acción y valores seguros por defecto |
| `src/lib/ai/agent.js` | Bucle del agente: llama a la función, aplica permisos, pide confirmación, devuelve resultados |
| `src/lib/ai/storage.js` | Conversación (y documentos autorizados) guardada en el dispositivo |
| `src/pages/Assistant.jsx` | Chat, tarjetas de confirmación y estado de cada acción |
| `src/components/AiSettings.jsx` | Ajustes → PACO AI |
| `supabase/functions/paco-ai/index.ts` | Edge Function: sesión, correo confirmado, límite diario, validación y llamada al modelo |

**Añadir una herramienta:** añade su esquema en el bloque `PACO_AI TOOLS` de la Edge Function, su tipo en `TOOL_KINDS` y su manejador en `createToolbox` (`tools.js`). `npm run test:ai` comprueba que ambos lados coinciden. Cualquier herramienta que cambie datos debe tener tipo `create`, `update` o `delete` para que pase por los permisos.

**Detalles de la integración con Groq** (REST `https://api.groq.com/openai/v1/chat/completions`, sin dependencias):

- Herramientas declaradas como `tools: [{ type: "function", function: { name, description, parameters } }]` con JSON Schema; `tool_choice: "auto"`.
- El navegador guarda la conversación en un formato interno propio (bloques `text` / `tool_use` / `tool_result`); la Edge Function lo traduce a mensajes `assistant` con `tool_calls` y mensajes `role: "tool"` con su `tool_call_id`, y de vuelta. Cambiar de proveedor solo requiere tocar la Edge Function.
- `reasoning_effort` (gpt-oss: `low` por defecto) e `include_reasoning: false` (el razonamiento no se devuelve: menos datos y más rapidez).
- Para caber en 8.000 tokens/minuto, los resultados de herramientas de mensajes anteriores se recortan y, si hace falta, se omiten los turnos más antiguos (nunca el mensaje actual). El modelo puede volver a pedir una herramienta.
- Errores: 500/502/503/504 y fallos de red → hasta 3 intentos con esperas crecientes; 429 por minuto con espera corta → espera `retry-after` y reintenta; `tool_use_failed` → un reintento; resto → mensaje claro. Ninguno gasta usos (si el primer paso falla, el uso se devuelve).

**Pruebas:** `npm run test:ai` (105 casos con un modelo simulado: no llama a ninguna API). Incluye la lectura de un PDF real de prueba (`scripts/fixtures/tema-redes.pdf`, con una instrucción maliciosa incrustada) y la creación de tareas a partir de él.
