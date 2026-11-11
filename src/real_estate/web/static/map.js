import { brl, int, pct } from './format.js'

const sequential = ['#fde68a', '#fcc867', '#f9a24b', '#f2773a', '#de4b30', '#b72a2a', '#7f1d1d']
const diverging = ['#1a7f4b', '#5fae6e', '#b9dcb1', '#d9d9d4', '#f6b38a', '#e46c4a', '#b3261e']
const gapBreaks = [-30, -15, -5, 5, 15, 30]
const empty = { type: 'FeatureCollection', features: [] }
const formats = { price: brl, price_m2: brl, gap_pct: pct }

const quantiles = values => {
  const sorted = values.filter(v => v != null).sort((a, b) => a - b)
  if (sorted.length < 7) return []
  return [1, 2, 3, 4, 5, 6].map(i => sorted[Math.floor(sorted.length * i / 7)])
}

const scale = (features, key) => {
  if (key === 'gap_pct') return { colors: diverging, breaks: gapBreaks }
  const breaks = [...new Set(quantiles(features.map(f => f.properties[key])))]
  return { colors: sequential.slice(sequential.length - breaks.length - 1), breaks }
}

const paint = (key, { colors, breaks }) => {
  const step = breaks.length ? ['step', ['get', key], colors[0], ...breaks.flatMap((b, i) => [b, colors[i + 1]])] : colors[0]
  return ['case', ['==', ['get', key], null], '#9a9a94', step]
}

const legend = (element, key, { colors, breaks }) => {
  const format = formats[key]
  const labels = colors.map((_, i) =>
    i === 0 ? `< ${format(breaks[0])}` : i === breaks.length ? `≥ ${format(breaks[i - 1])}` : `${format(breaks[i - 1])} – ${format(breaks[i])}`
  )
  element.innerHTML = colors.slice(0, breaks.length + 1)
    .map((c, i) => `<div class="row"><i style="background:${c}"></i>${labels[i]}</div>`).join('')
}

export const createMap = ({ onSelect, onHover, onArea, onEstimate }) => {
  const map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.openfreemap.org/styles/positron',
    center: [-51.1628, -23.3105],
    zoom: 13
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
  const tooltip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 })
  const ready = new Promise(resolve => map.on('load', resolve))
  let fitted = false
  let drawing = null

  ready.then(() => {
    map.addSource('listings', { type: 'geojson', data: empty })
    map.addSource('area', { type: 'geojson', data: empty })
    map.addLayer({ id: 'heat', type: 'heatmap', source: 'listings', layout: { visibility: 'none' },
      paint: { 'heatmap-radius': 18, 'heatmap-opacity': 0.7 } })
    map.addLayer({ id: 'area-fill', type: 'fill', source: 'area', paint: { 'fill-color': '#2459c9', 'fill-opacity': 0.08 } })
    map.addLayer({ id: 'area-line', type: 'line', source: 'area', paint: { 'line-color': '#2459c9', 'line-width': 2, 'line-dasharray': [2, 1] } })
    map.addLayer({ id: 'points', type: 'circle', source: 'listings', paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 3, 16, 7],
      'circle-stroke-color': ['case', ['get', 'favorite'], '#c99a06', '#ffffff'],
      'circle-stroke-width': ['case', ['get', 'favorite'], 2, 0.6],
      'circle-opacity': ['match', ['get', 'precision'], 'neighborhood', 0.35, 0.9]
    } })
    map.addLayer({ id: 'focus', type: 'circle', source: 'listings', filter: ['==', ['get', 'key'], ''], paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 7, 16, 12],
      'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#1d1d1b', 'circle-stroke-width': 2.5
    } })

    map.on('mousemove', 'points', event => {
      if (drawing) return
      const p = event.features[0].properties
      map.getCanvas().style.cursor = 'pointer'
      tooltip.setLngLat(event.lngLat).setHTML(`<b>${brl(p.price)}</b><br>${int(p.area)} m² · ${brl(p.price_m2)}/m²`).addTo(map)
      onHover(p.key)
    })
    map.on('mouseleave', 'points', () => {
      map.getCanvas().style.cursor = ''
      tooltip.remove()
      onHover(null)
    })
    map.on('click', 'points', event => {
      if (!drawing) onSelect(event.features[0].properties.key)
    })
    map.on('contextmenu', event => onEstimate(event.lngLat))
  })

  const outline = points => ({ type: 'FeatureCollection', features: points.length < 2 ? [] : [{
    type: 'Feature',
    geometry: points.length < 3
      ? { type: 'LineString', coordinates: points }
      : { type: 'Polygon', coordinates: [[...points, points[0]]] }
  }] })

  const finish = commit => {
    map.off('click', drawing.click)
    map.off('mousemove', drawing.move)
    map.off('dblclick', drawing.close)
    document.removeEventListener('keydown', drawing.key)
    map.doubleClickZoom.enable()
    document.getElementById('map').classList.remove('drawing')
    document.getElementById('hint').hidden = true
    const points = drawing.points
    drawing = null
    onArea(commit && points.length >= 3 ? points : undefined)
  }

  return {
    async render (collection, key, heat) {
      await ready
      const located = { type: 'FeatureCollection', features: collection.features.filter(f => f.geometry) }
      map.getSource('listings').setData(located)
      const s = scale(located.features, key)
      map.setPaintProperty('points', 'circle-color', paint(key, s))
      map.setLayoutProperty('heat', 'visibility', heat ? 'visible' : 'none')
      map.setLayoutProperty('points', 'visibility', heat ? 'none' : 'visible')
      legend(document.getElementById('legend'), key, s)
      if (!fitted && located.features.length) {
        const bounds = new maplibregl.LngLatBounds()
        located.features.forEach(f => bounds.extend(f.geometry.coordinates))
        map.fitBounds(bounds, { padding: 40, maxZoom: 15, duration: 0 })
        fitted = true
      }
    },
    async highlight (key) {
      await ready
      map.setFilter('focus', ['==', ['get', 'key'], key ?? ''])
    },
    fly (coordinates) {
      map.easeTo({ center: coordinates, zoom: Math.max(map.getZoom(), 15) })
    },
    async area (points) {
      await ready
      map.getSource('area').setData(outline(points ?? []))
    },
    draw () {
      if (drawing) return finish(false)
      drawing = { points: [] }
      map.doubleClickZoom.disable()
      document.getElementById('map').classList.add('drawing')
      document.getElementById('hint').hidden = false
      drawing.click = event => {
        const point = [+event.lngLat.lng.toFixed(5), +event.lngLat.lat.toFixed(5)]
        const last = drawing.points.at(-1)
        if (last && last[0] === point[0] && last[1] === point[1]) return
        drawing.points.push(point)
        map.getSource('area').setData(outline(drawing.points))
      }
      drawing.move = event => {
        map.getSource('area').setData(outline([...drawing.points, [event.lngLat.lng, event.lngLat.lat]]))
      }
      drawing.close = event => {
        event.preventDefault()
        finish(true)
      }
      drawing.key = event => {
        if (event.key === 'Escape') finish(false)
      }
      map.on('click', drawing.click)
      map.on('mousemove', drawing.move)
      map.on('dblclick', drawing.close)
      document.addEventListener('keydown', drawing.key)
    }
  }
}
