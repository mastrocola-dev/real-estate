import { get, list, set, toggle } from './state.js'
import { categories, precisions } from './format.js'

const ranges = { price: 'price', area: 'area', m2: 'm2', gap: 'gap' }
const checks = ['favorites', 'clean', 'heat']
const groups = ['category', 'source', 'precision']
const steps = [['', 'Todos'], ['1', '1+'], ['2', '2+'], ['3', '3+'], ['4', '4+']]

const chips = (element, key, options) => {
  element.innerHTML = ''
  options.forEach(([value, label]) => {
    const button = document.createElement('button')
    button.textContent = label
    button.dataset.value = value
    button.onclick = () => toggle(key, value)
    element.append(button)
  })
}

export const build = meta => {
  chips(document.getElementById('category'), 'category', meta.categories.map(c => [c, categories[c] ?? c]))
  document.getElementById('hoods').innerHTML = meta.neighborhoods.map(n => `<option value="${n}">`).join('')
  const hood = document.getElementById('hood')
  hood.onchange = () => {
    if (meta.neighborhoods.includes(hood.value) && !list('neighborhood').includes(hood.value)) toggle('neighborhood', hood.value)
    hood.value = ''
  }
  chips(document.getElementById('source'), 'source', meta.sources.map(s => [s.id, s.name.replace(/^Imobiliária /, '')]))
  chips(document.getElementById('precision'), 'precision', Object.entries(precisions))

  document.querySelectorAll('.range').forEach(element => {
    const key = ranges[element.dataset.key]
    element.innerHTML = ['min', 'max'].map(side =>
      `<input type="number" data-param="${key}_${side}" placeholder="${side === 'min' ? 'mín' : 'máx'}">`
    ).join('')
  })
  document.querySelectorAll('[data-param]').forEach(input => {
    input.onchange = () => set(input.dataset.param, input.value)
  })

  document.querySelectorAll('.min').forEach(element => {
    element.innerHTML = steps.map(([value, label]) => `<button data-value="${value}">${label}</button>`).join('')
    element.querySelectorAll('button').forEach(button => {
      button.onclick = () => set(element.dataset.key, button.dataset.value)
    })
  })

  document.querySelectorAll('#purpose button').forEach(button => {
    button.onclick = () => set('purpose', button.dataset.value)
  })
  document.querySelectorAll('[data-gap]').forEach(button => {
    button.onclick = () => {
      const [low, high] = button.dataset.gap.split(',')
      const active = get('gap_min') === low && get('gap_max') === high
      set('gap_min', active ? '' : low)
      set('gap_max', active ? '' : high)
    }
  })

  const q = document.getElementById('q')
  let timer
  q.oninput = () => {
    clearTimeout(timer)
    timer = setTimeout(() => set('q', q.value.trim()), 300)
  }
  checks.forEach(id => {
    document.getElementById(id).onchange = event => set(id, event.target.checked ? '1' : '')
  })
  document.getElementById('color').onchange = event => set('color', event.target.value)
  document.getElementById('sort').onchange = event => set('sort', event.target.value)
}

export const sync = () => {
  chips(document.getElementById('neighborhood'), 'neighborhood', list('neighborhood').map(n => [n, `${n} ×`]))
  document.querySelectorAll('#neighborhood button').forEach(b => b.classList.add('on'))
  groups.forEach(key => {
    const active = list(key)
    document.querySelectorAll(`#${key} button`).forEach(b => b.classList.toggle('on', active.includes(b.dataset.value)))
  })
  document.querySelectorAll('#purpose button').forEach(b => b.classList.toggle('on', b.dataset.value === get('purpose')))
  document.querySelectorAll('.min').forEach(element => {
    element.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.value === get(element.dataset.key)))
  })
  document.querySelectorAll('[data-param]').forEach(input => { input.value = get(input.dataset.param) })
  document.querySelectorAll('[data-gap]').forEach(button => {
    const [low, high] = button.dataset.gap.split(',')
    button.classList.toggle('on', get('gap_min') === low && get('gap_max') === high)
  })
  document.getElementById('q').value = get('q')
  checks.forEach(id => { document.getElementById(id).checked = get(id) === '1' })
  document.getElementById('color').value = get('color')
  document.getElementById('sort').value = get('sort')
}
