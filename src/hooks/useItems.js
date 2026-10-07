import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { onItemsChanged } from '../lib/runtimeContext'
import { useUI } from '../context/UIContext'

// Hook genérico de datos para cualquier módulo basado en items.
// Hace actualizaciones optimistas: la interfaz responde al instante.
export function useItems(module, { orderBy = 'created_at', ascending = false } = {}) {
  const { notifyError } = useUI()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  const reload = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true)
      try {
        setItems(await api.items.list({ module, orderBy, ascending }))
      } catch (e) {
        notifyError(e)
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [module, orderBy, ascending, notifyError],
  )

  useEffect(() => {
    reload()
  }, [reload])

  // Cambios hechos por la capa de datos (p. ej. la siguiente repetición de una tarea).
  useEffect(
    () => onItemsChanged((detail) => (!module || detail.module === module) && reload({ silent: true })),
    [module, reload],
  )

  const create = useCallback(
    async (fields) => {
      try {
        const row = await api.items.create({ module, ...fields })
        setItems((prev) => [row, ...prev])
        return row
      } catch (e) {
        notifyError(e)
        throw e
      }
    },
    [module, notifyError],
  )

  const update = useCallback(
    async (id, patch) => {
      let snapshot
      setItems((prev) => {
        snapshot = prev
        return prev.map((i) => (i.id === id ? { ...i, ...patch } : i))
      })
      try {
        const row = await api.items.update(id, patch)
        setItems((prev) => prev.map((i) => (i.id === id ? row : i)))
        return row
      } catch (e) {
        setItems(snapshot)
        notifyError(e)
        throw e
      }
    },
    [notifyError],
  )

  const remove = useCallback(
    async (id) => {
      let snapshot
      setItems((prev) => {
        snapshot = prev
        return prev.filter((i) => i.id !== id)
      })
      try {
        await api.items.remove(id)
      } catch (e) {
        setItems(snapshot)
        notifyError(e)
        throw e
      }
    },
    [notifyError],
  )

  return { items, loading, reload, create, update, remove, setItems }
}
