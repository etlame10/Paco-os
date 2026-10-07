# PACO AI — el asistente integrado en PACO OS

PACO AI es un chat (menú **PACO AI**, o el icono ✨ en el móvil) que consulta y organiza tus datos de PACO OS:

- «¿Qué tengo esta semana?» · «¿Qué tareas de prioridad alta tengo pendientes?»
- «Crea una tarea para mañana: llamar al banco» · «Recuérdame el viernes a las 18:00 ir al gimnasio»
- «Marca como hecha la práctica de física» · «Fija la nota del viaje» · «Borra la tarea de comprar pan»

Antes de crear, cambiar o borrar nada te enseña exactamente qué va a hacer y espera a que lo apruebes (configurable).

---

## Cómo funciona (y por qué es seguro)

```
Navegador (PACO OS)                         Supabase                       Anthropic
┌──────────────────────────┐   sesión   ┌───────────────────────┐  clave  ┌──────────┐
│ Chat + bucle del agente  │ ─────────► │ Edge Function paco-ai │ ──────► │ Claude   │
│ (src/lib/ai/agent.js)    │ ◄───────── │ · comprueba la sesión │ ◄────── │ (modelo) │
│                          │            │ · lista de emails     │         └──────────┘
│ Herramientas internas    │            │ · límite diario       │
│ (src/lib/ai/tools.js)    │            │ · guarda la clave     │
│  └─ api (RLS, avisos,    │            └───────────────────────┘
│     repeticiones)        │
└──────────────────────────┘
```

1. **La clave de la IA solo está en Supabase** (secreto de la Edge Function). Nunca en la web, en GitHub ni en el repositorio.
2. **El modelo no toca la base de datos.** Solo puede *pedir* una de 8 herramientas. Las ejecuta tu navegador con tu sesión, a través de la misma capa de datos que usa la app (`api`): RLS de Supabase (solo tus datos), avisos programados y repeticiones funcionan igual que si lo hicieras tú.
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

**Privacidad:** para responder, lo que PACO AI consulta (títulos, fechas, notas, nombres de archivos) se envía a Anthropic. El contenido de tus archivos nunca se envía. La conversación se guarda solo en tu dispositivo (botón «Nueva conversación» o Ajustes → PACO AI para borrarla). En Supabase solo se guarda un contador diario de uso (tabla `ai_usage`).

---

## Costes

> ⚠️ **Esto es lo único de PACO OS que no es gratis.** Supabase sigue en 0 € (1 invocación de Edge Function por paso; el plan gratuito incluye 500.000 al mes). La API de Claude es de pago por uso.

Precios de Anthropic (por millón de tokens, octubre 2026):

| Modelo (`PACO_AI_MODEL`) | Entrada | Salida | Coste aproximado por mensaje* |
| --- | --- | --- | --- |
| `claude-opus-5-5` (por defecto, el más capaz) | 4 $ | 20 $ | ~0,03–0,08 $ |
| `claude-sonnet-5-5` (equilibrado) | 2 $ | 10 $ | ~0,015–0,04 $ |
| `claude-haiku-4-5` (el más económico) | 1 $ | 5 $ | ~0,005–0,02 $ |

\* Estimación para una pregunta típica (2–3 pasos). Depende de la longitud de la conversación; la caché automática abarata los pasos siguientes. Con 20 mensajes al día y el modelo por defecto serían unos 20–45 $ al mes; con Sonnet, la mitad.

Para controlar el gasto:

- **Pon un límite de gasto mensual** en la consola de Anthropic (Settings → Limits). Es la protección más importante: aunque algo fallara, nunca pagarías más de esa cifra.
- `PACO_AI_DAILY_LIMIT` (por defecto 150 peticiones/día por usuario).
- `PACO_AI_MODEL=claude-sonnet-5-5` o `PACO_AI_EFFORT=low` para gastar menos.
- Empieza conversaciones nuevas cuando cambies de tema (las largas cuestan más por mensaje).

---

## Activarlo (una vez, ~10 minutos)

### 1. Base de datos

Supabase → **SQL Editor** → ejecuta la **sección 8** de `supabase/schema.sql` (o el archivo completo: es idempotente y no borra nada). Crea la tabla `ai_usage` y dos funciones que solo puede usar la Edge Function.

### 2. Clave de la API de Claude

1. Crea una cuenta en https://console.anthropic.com y añade saldo.
2. **Settings → Limits**: fija un límite de gasto mensual.
3. **API Keys → Create Key**. Cópiala (empieza por `sk-ant-…`). **No la pegues en GitHub, en `.env` ni en ningún archivo del proyecto.**

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
| `ANTHROPIC_API_KEY` | Sí | Tu clave `sk-ant-…` |
| `PACO_AI_ALLOWED_EMAILS` | Sí | Tu email de PACO OS (varios separados por comas) |
| `PACO_AI_DAILY_LIMIT` | No | Peticiones por usuario y día (150) |
| `PACO_AI_MODEL` | No | `claude-opus-5-5` (por defecto), `claude-sonnet-5-5`, `claude-haiku-4-5` |
| `PACO_AI_EFFORT` | No | `low`, `medium` (por defecto) o `high`. No aplica a Haiku |

No hace falta tocar GitHub ni volver a desplegar la web: el frontend no necesita ninguna variable nueva.

### 5. Comprobar

Abre PACO OS → **Ajustes → PACO AI**. Debe decir «Activo · modelo … · hoy 0/150 peticiones». Si no, el mensaje indica qué falta.

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

**Detalles de la integración con Claude:**

- Una petición a la API por paso, con `cache_control` automático (el historial se reutiliza de la caché).
- Razonamiento adaptativo del modelo (por defecto en Opus 5.5) y esfuerzo configurable (`PACO_AI_EFFORT`).
- `fallbacks: "default"`: si el modelo rechaza una petición por sus filtros de seguridad, Anthropic la reintenta automáticamente en el modelo recomendado.
- El historial **solo crece** (nunca se edita ni recorta) y se reenvía íntegro, incluidos los bloques de razonamiento: es lo que exige la API para conservarlo entre pasos. Por eso las conversaciones muy largas piden empezar una nueva.

**Pruebas:** `npm run test:ai` (62 casos con un modelo simulado: no llama a ninguna API ni gasta).
