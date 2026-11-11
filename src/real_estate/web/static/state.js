const defaults = { purpose: 'sale', color: 'price_m2', sort: 'price_m2' }
const view = ['color', 'heat', 'sort']
const params = new URLSearchParams(location.search)
const listeners = []

export const get = key => params.get(key) ?? defaults[key] ?? ''
export const list = key => get(key).split(',').filter(Boolean)

export const set = (key, value) => {
  if (value === '' || value == null || value === false) params.delete(key)
  else params.set(key, value)
  history.replaceState(null, '', `?${params}`)
  listeners.forEach(listener => listener(key))
}

export const toggle = (key, value) => {
  const items = list(key)
  set(key, (items.includes(value) ? items.filter(item => item !== value) : [...items, value]).join(','))
}

export const reset = () => {
  const keep = ['purpose', ...view].filter(key => params.has(key)).map(key => [key, params.get(key)])
  Array.from(params.keys()).forEach(key => params.delete(key))
  keep.forEach(([key, value]) => params.set(key, value))
  set('purpose', get('purpose'))
}

export const isView = key => view.includes(key)
export const listen = listener => listeners.push(listener)

export const query = () => {
  const result = new URLSearchParams(params)
  result.set('purpose', get('purpose'))
  view.forEach(key => result.delete(key))
  return result
}
