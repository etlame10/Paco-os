import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Trash2, Puzzle, ChevronUp, ChevronDown, ArrowRight } from 'lucide-react'
import ModuleHeader from '../components/ModuleHeader'
import ModuleBuilder from '../components/ModuleBuilder'
import { ModuleIcon } from '../components/ui'
import { useSettings } from '../context/SettingsContext'
import { useUI } from '../context/UIContext'
import { api } from '../lib/api'

// "Tienda" de módulos: activar, desactivar, ordenar y crear módulos propios.
export default function ModulesStore() {
  const { modules, settings, enabledModules, toggleModule, moveModule, update } = useSettings()
  const { confirm, toast, notifyError } = useUI()
  const [builder, setBuilder] = useState(null) // null | 'new' | def

  const categories = [...new Set(modules.map((m) => m.category || 'Otros'))]

  const saveCustom = (def) => {
    update((prev) => {
      const exists = prev.customModules.some((m) => m.id === def.id)
      return {
        customModules: exists ? prev.customModules.map((m) => (m.id === def.id ? def : m)) : [...prev.customModules, def],
        enabledModules: exists ? prev.enabledModules : [...prev.enabledModules, def.id],
      }
    })
    toast(builder === 'new' ? `Módulo "${def.name}" creado` : 'Módulo actualizado')
  }

  const deleteCustom = async (m) => {
    try {
      const items = await api.items.list({ module: m.id })
      const ok = await confirm(
        items.length
          ? `Se eliminará el módulo "${m.name}" y sus ${items.length} elementos. Esta acción no se puede deshacer.`
          : `Se eliminará el módulo "${m.name}".`,
      )
      if (!ok) return
      for (const it of items) await api.items.remove(it.id)
      update((prev) => ({
        customModules: prev.customModules.filter((x) => x.id !== m.id),
        enabledModules: prev.enabledModules.filter((x) => x !== m.id),
      }))
      toast('Módulo eliminado')
    } catch (e) {
      notifyError(e)
    }
  }

  return (
    <div className="page">
      <ModuleHeader
        module={{ icon: Puzzle, color: 'var(--accent)' }}
        title="Módulos"
        subtitle="PACO OS crece contigo: activa los módulos que necesites o crea los tuyos propios sin programar."
        actions={
          <button className="btn primary" onClick={() => setBuilder('new')}>
            <Plus size={18} /> <span className="hide-sm">Crear módulo</span>
          </button>
        }
      />

      <section className="card">
        <h3 className="section-title">Orden del menú</h3>
        <div className="list compact">
          {enabledModules.map((m, i) => (
            <div key={m.id} className="row">
              <ModuleIcon module={m} size={16} />
              <span className="row-main">{m.name}</span>
              <button className="icon-btn sm" disabled={i === 0} onClick={() => moveModule(m.id, -1)} aria-label="Subir">
                <ChevronUp size={16} />
              </button>
              <button className="icon-btn sm" disabled={i === enabledModules.length - 1} onClick={() => moveModule(m.id, 1)} aria-label="Bajar">
                <ChevronDown size={16} />
              </button>
            </div>
          ))}
          {!enabledModules.length && <p className="muted small">No hay módulos activos.</p>}
        </div>
      </section>

      {categories.map((cat) => (
        <section key={cat} className="store-section">
          <h3 className="section-title">{cat}</h3>
          <div className="store-grid">
            {modules
              .filter((m) => (m.category || 'Otros') === cat)
              .map((m) => {
                const on = settings.enabledModules.includes(m.id)
                return (
                  <div key={m.id} className={`card store-card ${on ? 'on' : ''}`} style={{ '--mod': m.color }}>
                    <div className="store-card-head">
                      <ModuleIcon module={m} size={20} />
                      <div className="row-main">
                        <strong>{m.name}</strong>
                        {m.custom && <span className="badge">Personalizado</span>}
                      </div>
                      <label className="switch" title={on ? 'Desactivar' : 'Activar'}>
                        <input type="checkbox" checked={on} onChange={(e) => toggleModule(m.id, e.target.checked)} />
                        <span />
                      </label>
                    </div>
                    <p className="muted small">{m.description}</p>
                    <div className="store-card-actions">
                      {on && (
                        <Link to={`/m/${m.id}`} className="btn ghost xs">
                          Abrir <ArrowRight size={13} />
                        </Link>
                      )}
                      {m.custom && (
                        <>
                          <button className="btn ghost xs" onClick={() => setBuilder(m.raw)}>
                            <Pencil size={13} /> Editar
                          </button>
                          <button className="btn ghost xs danger-text" onClick={() => deleteCustom(m)}>
                            <Trash2 size={13} /> Eliminar
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
        </section>
      ))}

      <button className="card store-create" onClick={() => setBuilder('new')}>
        <Plus size={22} />
        <div>
          <strong>Crea tu propio módulo</strong>
          <p className="muted small">Libros, recetas, gimnasio, mascotas, coches, colecciones… define los campos y listo.</p>
        </div>
      </button>

      {builder && (
        <ModuleBuilder
          initial={builder === 'new' ? null : builder}
          existingIds={modules.map((m) => m.id)}
          onSave={saveCustom}
          onClose={() => setBuilder(null)}
        />
      )}
    </div>
  )
}
