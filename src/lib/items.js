// Utilidades para trabajar con "items" genéricos.
// Los campos núcleo viven en columnas propias; el resto, dentro de item.data.
export const CORE_KEYS = ['title', 'body', 'status', 'due_date', 'tags']

export const getField = (item, key) => (CORE_KEYS.includes(key) ? item?.[key] : item?.data?.[key])

// Convierte un objeto plano {campo: valor} del formulario en columnas + data.
export function formToItem(values, baseData = {}) {
  const out = { data: { ...baseData } }
  for (const [k, v] of Object.entries(values)) {
    if (CORE_KEYS.includes(k)) out[k] = v
    else if (v === '' || v === null || v === undefined) delete out.data[k]
    else out.data[k] = v
  }
  if (out.due_date === '') out.due_date = null
  if (out.status === '') out.status = null
  return out
}

export function itemToForm(item, fields) {
  const v = {}
  for (const f of fields) {
    const val = getField(item, f.key)
    v[f.key] = val ?? (f.type === 'tags' ? [] : '')
  }
  return v
}

export function defaultForm(fields, overrides = {}) {
  const v = {}
  for (const f of fields) {
    const d = typeof f.default === 'function' ? f.default() : f.default
    v[f.key] = d ?? (f.type === 'tags' ? [] : '')
  }
  return { ...v, ...overrides }
}

export function statusOption(module, value) {
  const f = module.fields?.find((x) => x.key === 'status')
  return f?.options?.find((o) => o.value === value)
}

export function optionLabel(field, value) {
  return field.options?.find((o) => o.value === value)?.label ?? value
}
