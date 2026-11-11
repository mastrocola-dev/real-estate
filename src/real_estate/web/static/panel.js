import { brl, categories, escape, int, pct, precisions, purposes, summary, tone } from './format.js'

const page = 200
const listView = document.getElementById('list-view')
const detail = document.getElementById('detail')
const list = document.getElementById('list')
const more = document.getElementById('more')

const compare = sort => {
  const key = sort.replace('-', '')
  const sign = sort.startsWith('-') ? -1 : 1
  return (a, b) => {
    const x = a.properties[key]
    const y = b.properties[key]
    if (x == null) return 1
    if (y == null) return -1
    return sign * (x - y)
  }
}

const item = p => `
  <li data-key="${p.key}">
    <span class="title">${p.favorite ? '<span class="star">★</span> ' : ''}${categories[p.category] ?? p.category}${p.address ? ` · ${escape(p.address)}` : ''}</span>
    <span class="price">${brl(p.price)}</span>
    <span class="meta">${summary(p)} · ${escape(p.agency.replace(/^Imobiliária /, ''))}</span>
    <span class="meta">${brl(p.price_m2)}/m²</span>
    <span class="meta">${escape(p.neighborhood ?? '')}${p.precision === 'neighborhood' ? ' · sem posição' : ''}</span>
    <span class="gap ${tone(p.gap_pct)}">${p.gap_pct == null ? '' : `${pct(p.gap_pct)} vs modelo`}</span>
  </li>`

const sparkline = points => {
  if (points.length < 2) return ''
  const xs = points.map(p => new Date(p.observed_at).getTime())
  const ys = points.map(p => p.price)
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const path = points.map((p, i) => {
    const x = x1 === x0 ? 0 : (xs[i] - x0) / (x1 - x0) * 300
    const y = y1 === y0 ? 40 : 75 - (ys[i] - y0) / (y1 - y0) * 70
    return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join('')
  return `<svg viewBox="0 0 300 80" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="#2459c9" stroke-width="2"/></svg>`
}

const offer = (o, history) => `
  <div class="offer">
    <div>${purposes[o.purpose]}</div>
    <div class="big">${brl(o.price)}</div>
    <div>${brl(o.price_m2)}/m²</div>
    ${o.model_price == null ? '' : `<div>Modelo: ${brl(o.model_price)} <span class="${tone(o.gap_pct)}">(${pct(o.gap_pct)})</span></div>`}
    ${o.outlier ? '<div class="bad">Marcado como outlier</div>' : ''}
    ${o.duplicate ? '<div>Provável duplicado em outra imobiliária</div>' : ''}
    ${sparkline(history.filter(h => h.purpose === o.purpose))}
  </div>`

export const createPanel = ({ onHover, onSelect, onFavorite, onClose }) => {
  let items = []
  let shown = page

  const draw = () => {
    list.innerHTML = items.slice(0, shown).map(f => item(f.properties)).join('')
    more.hidden = items.length <= shown
  }

  list.addEventListener('mouseover', event => {
    const li = event.target.closest('li')
    if (li) onHover(li.dataset.key)
  })
  list.addEventListener('mouseleave', () => onHover(null))
  list.addEventListener('click', event => {
    const li = event.target.closest('li')
    if (li) onSelect(li.dataset.key)
  })
  more.onclick = () => {
    shown += page
    draw()
  }

  const open = html => {
    detail.innerHTML = `<button class="back">← Voltar à lista</button>${html}`
    detail.querySelector('.back').onclick = onClose
    listView.hidden = true
    detail.hidden = false
    detail.scrollTop = 0
  }

  return {
    render (features, sort) {
      items = [...features].sort(compare(sort))
      shown = page
      draw()
    },
    hover (key) {
      list.querySelectorAll('li.hover').forEach(li => li.classList.remove('hover'))
      if (key) list.querySelector(`li[data-key="${key}"]`)?.classList.add('hover')
    },
    show ({ offers, history }) {
      const p = offers[0]
      open(`
        <h2>${categories[p.category] ?? p.category} · ${escape(p.neighborhood ?? '')}</h2>
        <div>${escape(p.address ?? 'Endereço não informado')}</div>
        ${offers.map(o => offer(o, history)).join('')}
        <dl>
          <dt>Tipo no anúncio</dt><dd>${escape(p.type ?? '—')}</dd>
          <dt>Área</dt><dd>${int(p.area)} m²</dd>
          <dt>Quartos</dt><dd>${int(p.bedrooms)}</dd>
          <dt>Suítes</dt><dd>${int(p.suites)}</dd>
          <dt>Banheiros</dt><dd>${int(p.bathrooms)}</dd>
          <dt>Vagas</dt><dd>${int(p.parking)}</dd>
          <dt>Imobiliária</dt><dd>${escape(p.agency)}</dd>
          <dt>Código</dt><dd>${escape(p.code)}</dd>
          <dt>Localização</dt><dd>${precisions[p.precision] ?? '—'}</dd>
          <dt>Visto em</dt><dd>${new Date(p.observed_at).toLocaleDateString('pt-BR')}</dd>
        </dl>
        <a href="${escape(p.url)}" target="_blank" rel="noopener">Abrir no site da imobiliária ↗</a>
        <button class="favorite ${p.favorite ? 'on' : ''}">${p.favorite ? '★ Favorito' : '☆ Favoritar'}</button>
        <textarea placeholder="Notas sobre este imóvel">${escape(p.note ?? '')}</textarea>`)
      const note = detail.querySelector('textarea')
      detail.querySelector('.favorite').onclick = () => onFavorite(p.id, !p.favorite, note.value)
      note.onchange = () => onFavorite(p.id, true, note.value)
    },
    estimate ({ lngLat, purpose, categoriesList, submit }) {
      const options = categoriesList.map(c => `<option value="${c}">${categories[c] ?? c}</option>`).join('')
      const field = (name, label, value) => `<label>${label}<input type="number" name="${name}" value="${value}" min="0"></label>`
      open(`
        <h2>Avaliar um imóvel</h2>
        <div>Ponto: ${lngLat.lat.toFixed(5)}, ${lngLat.lng.toFixed(5)} · ${purposes[purpose]}</div>
        <form class="estimate">
          <label>Tipo<select name="category">${options}</select></label>
          ${field('area', 'Área (m²)', 80)}
          ${field('bedrooms', 'Quartos', 2)}
          ${field('suites', 'Suítes', 1)}
          ${field('bathrooms', 'Banheiros', 2)}
          ${field('parking', 'Vagas', 1)}
          <button>Estimar</button>
        </form>
        <div class="result"></div>
        <small>Regressão hedônica sobre os anúncios atuais. Não considera condomínio, idade nem andar.</small>`)
      const form = detail.querySelector('form')
      form.category.value = categoriesList.includes('apartment') ? 'apartment' : categoriesList[0]
      form.onsubmit = async event => {
        event.preventDefault()
        const result = await submit(Object.fromEntries(new FormData(form)))
        detail.querySelector('.result').innerHTML = `<div class="big">${brl(result.price)}</div><div>${brl(result.price_m2)}/m²</div>`
      }
    },
    close () {
      detail.hidden = true
      listView.hidden = false
    }
  }
}
