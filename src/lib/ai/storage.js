// La conversación de PACO AI se guarda solo en este dispositivo (no en Supabase).
const keyFor = (userId) => `pacoos.ai.chat.${userId}`

export function loadChat(userId) {
  try {
    const c = JSON.parse(localStorage.getItem(keyFor(userId)))
    if (Array.isArray(c?.messages)) {
      return {
        messages: c.messages,
        actions: c.actions || {},
        approved: Array.isArray(c.approved) ? c.approved : [],
        // Interacción en curso: «Continuar» o «Reintentar» tras recargar no gastan otro uso.
        interaction: typeof c.interaction === 'string' ? c.interaction : null,
      }
    }
  } catch {
    /* sin conversación guardada */
  }
  return { messages: [], actions: {}, approved: [], interaction: null }
}

export function saveChat(userId, chat) {
  try {
    if (chat.messages.length) localStorage.setItem(keyFor(userId), JSON.stringify(chat))
    else localStorage.removeItem(keyFor(userId))
  } catch {
    /* almacenamiento lleno o bloqueado: la conversación sigue en memoria */
  }
}

export function clearChat(userId) {
  try {
    localStorage.removeItem(keyFor(userId))
  } catch {
    /* nada que borrar */
  }
}
