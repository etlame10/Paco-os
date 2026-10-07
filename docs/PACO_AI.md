# PACO AI — el asistente integrado en PACO OS

PACO AI es un chat (menú **PACO AI**, o el icono ✨ en el móvil) que consulta y organiza tus datos de PACO OS:

- «¿Qué tengo esta semana?» · «¿Qué tareas de prioridad alta tengo pendientes?»
- «Crea una tarea para mañana: llamar al banco» · «Recuérdame el viernes a las 18:00 ir al gimnasio»
- «Marca como hecha la práctica de física» · «Fija la nota del viaje» · «Borra la tarea de comprar pan»

Antes de crear, cambiar o borrar nada te enseña exactamente qué va a hacer y espera a que lo apruebes (configurable).

---

## Cómo funciona (y por qué es seguro)

```
Navegador (PACO OS)                         Supabase                       Google
┌──────────────────────────┐   sesión   ┌───────────────────────┐  clave  ┌──────────┐
│ Chat + bucle del agente  │ ─────────► │ Edge Function paco-ai │ ──────► │ Gemini   │
│ (src/lib/ai/agent.js)    │ ◄───────── │ · comprueba la sesión │ ◄────── │   API    │
│                          │            │ · lista de emails     │         └──────────┘
│ Herramientas internas    │            │ · límite diario       │
│ (src/lib/ai/tools.js)    │            │ · guarda la clave     │
│  └─ api (RLS, avisos,    │            └───────────────────────┘
│     repeticiones)        │
└──────────────────────────┘
```

1. **La clave de Gemini solo está en Supabase** (secreto `GEMINI_API_KEY` de la Edge Function). Viaja a Google en una cabecera, nunca en la URL. Nunca en la web, en GitHub ni en el repositorio.
2. **El modelo no toca la base de datos.** Solo puede *pedir* una de 8 herramientas (function calling de Gemini). Las ejecuta tu navegador con tu sesión, a través de la misma capa de datos que usa la app (`api`): RLS de Supabase (solo tus datos), avisos programados y repeticiones funcionan igual que si lo hicieras tú.
3. **Validación estricta.** Cada petición se comprueba contra la definición del módulo (campos existentes, tipos, opciones válidas, fechas reales…). Si no es válida, el modelo recibe el error y la corrige; no se te pregunta nada.
4. **Permisos aplicados por código, no por la IA** (Ajustes → PACO AI):

   | Acción | Por defecto | Opciones |
   | --- | --- | --- |
   | Consultar (buscar, agenda, nombres de archivos) | Sin preguntar | Sin preguntar · No permitir |
   | Crear elementos | **Preguntar** | Preguntar · Sin preguntar · No permitir |
   | Editar elementos | **Preguntar** | Preguntar · Sin preguntar · No permitir |
   | Eliminar elementos | **Preguntar** | Preguntar · No permitir (nunca sin preguntar) |

5. **Límites de seguridad:** máximo 15 cambios y 10 llamadas al modelo por cada mensaje tuyo; solo módulos activos; no puede tocar ajustes, módulos, archivos (solo ve sus nombres) ni contraseñas.
6. **Inyección de instrucciones:** si una nota dice «borra todo», el modelo tiene instrucciones de tratarlo como dato, y aunque lo intentara, borrar exige tu confirmación.
7. **Solo tú (o quien elijas):** la función rechaza a cualquier usuario cuyo email no esté en `PACO_AI_ALLOWED_EMAILS`, y limita las peticiones diarias (`PACO_AI_DAILY_LIMIT`).

**Privacidad:** para responder, lo que PACO AI consulta (títulos, fechas, notas, nombres de archivos) se envía a Google (Gemini API). El contenido de tus archivos nunca se envía. La conversación se guarda solo en tu dispositivo (botón «Nueva conversación» o Ajustes → PACO AI para borrarla). En Supabase solo se guarda un contador diario de uso (tabla `ai_usage`).

---

## Costes y nivel gratuito de Gemini

PACO AI usa **Gemini API con su nivel gratuito**: sin tarjeta y sin ningún servicio de pago. Supabase sigue en 0 € (1 invocación de Edge Function por paso; el plan gratuito incluye 500.000 al mes).

**Cuánto da de sí el nivel gratuito.** Google aplica límites por proyecto de peticiones por minuto (RPM), por día (RPD) y de tokens por minuto. Los cambia a menudo y los muestra para tu proyecto en **Google AI Studio → Usage / Rate limits**: esa es la cifra válida para ti. Cada mensaje tuyo suele costar **2–3 peticiones** (consultar + responder; crear algo y confirmar), así que:

| Límite diario del modelo (RPD) | Mensajes aproximados al día |
| --- | --- |
| 20 | ~7–10 |
| 250 | ~80–120 |
| 1.000 | ~350–500 |

Si un día se agota la cuota, PACO AI lo dice («Se ha agotado la cuota de Gemini…») y vuelve a funcionar cuando Google la reinicia (cada día a medianoche, hora del Pacífico). Nada se cobra.

**Si se te queda corto**, sin tocar la web:

- `PACO_AI_MODEL=gemini-3.5-flash-lite` (u otro Flash-Lite): modelos más ligeros con más cuota gratuita.
- `PACO_AI_THINKING=minimal` o `low`: respuestas más rápidas y con menos tokens.
- `PACO_AI_DAILY_LIMIT`: tu propio tope diario por usuario (por defecto 100 peticiones), para repartir la cuota.

> ⚠️ **Condiciones de Google para Europa.** Los términos adicionales de Gemini API dicen que, al ofrecer una aplicación a usuarios del Espacio Económico Europeo, Suiza o Reino Unido, solo se pueden usar los «Paid Services» (proyecto con facturación activa). PACO OS es una herramienta personal que usas tú; revisa esos términos (https://ai.google.dev/gemini-api/terms) y decide si necesitas activar la facturación. Activarla no tiene coste fijo: se paga por uso y puedes poner un presupuesto. Ventaja que sí aplica ya en la UE: según esos mismos términos, en el EEE/Suiza/Reino Unido Google trata tus datos como en el plan de pago (**no los usa para mejorar sus productos**), aunque uses la cuota gratuita.

## Activarlo (una vez, ~10 minutos)

### 1. Base de datos

Supabase → **SQL Editor** → ejecuta la **sección 8** de `supabase/schema.sql` (o el archivo completo: es idempotente y no borra nada). Crea la tabla `ai_usage` y dos funciones que solo puede usar la Edge Function.

### 2. Clave de Gemini API (gratis)

1. Entra en https://aistudio.google.com/apikey con tu cuenta de Google y pulsa **Create API key** (no pide tarjeta).
2. Cópiala (empieza por `AIza…`). **No la pegues en GitHub, en `.env` ni en ningún archivo del proyecto.**
3. En AI Studio puedes consultar los límites gratuitos de tu proyecto para cada modelo.

### 3. Edge Function `paco-ai`

Supabase → **Edge Functions → Deploy a new function → Via Editor**:

1. Nombre: `paco-ai`.
2. Pega el contenido de `supabase/functions/paco-ai/index.ts` y despliega.
3. En los ajustes de la función, **desactiva «Verify JWT»** (la función comprueba ella misma tu sesión).

(Con la CLI: `supabase functions deploy paco-ai --no-verify-jwt`.)

### 4. Secretos

Supabase → **Edge Functions → Secrets** (o `supabase secrets set NOMBRE=valor`):

| Secreto | Obligatorio | Valor |
| --- | --- | --- |
| `GEMINI_API_KEY` | Sí | Tu clave `AIza…` de Google AI Studio |
| `PACO_AI_ALLOWED_EMAILS` | Sí | Tu email de PACO OS (varios separados por comas) |
| `PACO_AI_DAILY_LIMIT` | No | Peticiones por usuario y día (100) |
| `PACO_AI_MODEL` | No | Modelo de Gemini. Por defecto `gemini-3.8-flash` |
| `PACO_AI_THINKING` | No | `minimal`, `low`, `medium` o `high`. Por defecto, el del modelo |

No hace falta tocar GitHub ni volver a desplegar la web: el frontend no necesita ninguna variable nueva.

### 5. Comprobar

Abre PACO OS → **Ajustes → PACO AI**. Debe decir «Activo · modelo gemini-3.8-flash · hoy 0/100 peticiones». Si no, el mensaje indica qué falta.

---

## Para desarrolladores

| Archivo | Qué hace |
| --- | --- |
| `src/lib/ai/tools.js` | Herramientas internas: validación y ejecución sobre `api` (tipos `read`/`create`/`update`/`delete`) |
| `src/lib/ai/permissions.js` | Permisos por tipo de acción y valores seguros por defecto |
| `src/lib/ai/agent.js` | Bucle del agente: llama a la función, aplica permisos, pide confirmación, devuelve resultados |
| `src/lib/ai/storage.js` | Conversación guardada en el dispositivo |
| `src/pages/Assistant.jsx` | Chat, tarjetas de confirmación y estado de cada acción |
| `src/components/AiSettings.jsx` | Ajustes → PACO AI |
| `supabase/functions/paco-ai/index.ts` | Edge Function: sesión, lista de emails, límite diario, validación y llamada al modelo |

**Añadir una herramienta:** añade su esquema en el bloque `PACO_AI TOOLS` de la Edge Function, su tipo en `TOOL_KINDS` y su manejador en `createToolbox` (`tools.js`). `npm run test:ai` comprueba que ambos lados coinciden. Cualquier herramienta que cambie datos debe tener tipo `create`, `update` o `delete` para que pase por los permisos.

**Detalles de la integración con Gemini** (REST `v1beta/models/{modelo}:generateContent`, sin dependencias):

- Herramientas declaradas como `functionDeclarations` con `parametersJsonSchema`; modo `AUTO` (el modelo decide si usar herramientas o responder).
- El navegador guarda la conversación en un formato interno propio (bloques `text` / `tool_use` / `tool_result`); la Edge Function lo traduce a `contents` / `functionCall` / `functionResponse` y de vuelta. Cambiar de proveedor solo requiere tocar la Edge Function.
- **Thought signatures:** Gemini firma su razonamiento (`thoughtSignature`) junto a cada `functionCall`. Se guardan en el bloque (`signature`) y se le devuelven intactas; el historial **solo crece** (nunca se edita ni recorta). Por eso las conversaciones muy largas piden empezar una nueva.
- Si Gemini da un `id` a la llamada, se devuelve en el `functionResponse`; los errores de herramienta van en `response.error`.
- Finalizaciones especiales: `SAFETY`/`PROHIBITED_CONTENT` → «no puedo ayudarte», `MAX_TOKENS` → aviso de respuesta cortada, llamada mal formada → pide reformular.
- Un reintento automático ante un 500/503 puntual de Google.

**Pruebas:** `npm run test:ai` (64 casos con un modelo simulado: no llama a ninguna API).
