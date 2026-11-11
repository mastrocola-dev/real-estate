import { build, sync } from './filters.js'
import { createMap } from './map.js'
import { createPanel } from './panel.js'
import { get, isView, listen, query, reset, set } from './state.js'

const json = async (url, options) => {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error(`${response.status} ${url}`)
  return response.json()
}

const parseArea = value => value ? value.split(';').map(pair => pair.split(',').map(Number)) : null
const serializeArea = points => points.map(p => p.join(',')).join(';')

let collection = { type: 'FeatureCollection', features: [] }
let meta
let selected = null
const byKey = key => collection.features.find(f => f.properties.key === key)

const map = createMap({
  onSelect: key => select(key),
  onHover: key => panel.hover(key),
  onArea: points => {
    if (points === undefined) return map.area(parseArea(get('polygon')))
    set('polygon', points ? serializeArea(points) : '')
  },
  onEstimate: lngLat => panel.estimate({
    lngLat,
    purpose: get('purpose'),
    categoriesList: meta.categories,
    submit: values => json(`/api/estimate?${new URLSearchParams({ ...values, purpose: get('purpose'), lat: lngLat.lat, lon: lngLat.lng })}`)
  })
})

const panel = createPanel({
  onHover: key => map.highlight(key),
  onSelect: key => select(key),
  onClose: () => {
    selected = null
    map.highlight(null)
    panel.close()
  },
  onFavorite: async (id, on, note) => {
    await json(`/api/favorites/${id}`, on
      ? { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ note }) }
      : { method: 'DELETE' })
    await load()
    if (selected) select(selected)
  }
})

const select = async key => {
  selected = key
  map.highlight(key)
  const feature = byKey(key)
  if (feature?.geometry) map.fly(feature.geometry.coordinates)
  panel.show(await json(`/api/listings/${key.split(':')[0]}`))
}

const draw = () => {
  map.render(collection, get('color'), get('heat') === '1')
  panel.render(collection.features, get('sort'))
  const located = collection.features.filter(f => ['exact', 'street'].includes(f.properties.precision)).length
  document.getElementById('count').textContent = `${collection.features.length} anúncios · ${located} com posição`
}

const load = async () => {
  collection = await json(`/api/listings?${query()}`)
  draw()
}

let timer
listen(key => {
  sync()
  if (key === 'polygon') map.area(parseArea(get('polygon')))
  if (isView(key)) return draw()
  clearTimeout(timer)
  timer = setTimeout(load, 150)
})

document.getElementById('draw').onclick = () => map.draw()
document.getElementById('reset').onclick = () => reset()

meta = await json('/api/meta')
build(meta)
sync()
map.area(parseArea(get('polygon')))
await load()
