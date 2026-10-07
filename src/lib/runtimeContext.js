// La capa de datos (src/lib/api) no conoce React. SettingsContext le pasa aquí los
// módulos y ajustes actuales para que avisos y repeticiones sepan cómo actuar.
let context = { getModule: () => null, settings: null }

export function setRuntimeContext(ctx) {
  context = ctx
}

export function getRuntimeContext() {
  return context
}

// Aviso ligero de cambios en elementos hechos fuera del flujo normal de una vista
// (p. ej. la siguiente repetición de una tarea), para que las listas se recarguen.
const listeners = new Set()

export function onItemsChanged(cb) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function emitItemsChanged(detail) {
  listeners.forEach((cb) => {
    try {
      cb(detail)
    } catch (e) {
      console.warn(e)
    }
  })
}
