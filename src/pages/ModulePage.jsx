import { Link, useParams } from 'react-router-dom'
import { Puzzle } from 'lucide-react'
import { useSettings } from '../context/SettingsContext'
import { EmptyState } from '../components/ui'
import CollectionView from '../modules/views/CollectionView'

// Resuelve /m/:moduleId -> componente propio del módulo o la vista genérica de colección.
export default function ModulePage() {
  const { moduleId } = useParams()
  const { getModule, settings, toggleModule } = useSettings()
  const module = getModule(moduleId)

  if (!module) {
    return (
      <div className="page">
        <EmptyState icon={Puzzle} title="Módulo no encontrado" text="Puede que se haya eliminado." action={<Link className="btn primary" to="/modulos">Ver módulos</Link>} />
      </div>
    )
  }

  if (!settings.enabledModules.includes(module.id)) {
    return (
      <div className="page">
        <EmptyState
          icon={module.icon}
          title={`${module.name} está desactivado`}
          text={module.description}
          action={
            <button className="btn primary" onClick={() => toggleModule(module.id, true)}>
              Activar módulo
            </button>
          }
        />
      </div>
    )
  }

  const View = module.component || CollectionView
  return <View key={module.id} module={module} />
}
