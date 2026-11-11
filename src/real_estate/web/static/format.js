const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

export const brl = value => value == null ? '—' : money.format(value)
export const int = value => value == null ? '—' : number.format(value)
export const pct = value => value == null ? '—' : `${value > 0 ? '+' : ''}${number.format(value)}%`
export const tone = value => value == null ? '' : value <= -10 ? 'good' : value >= 10 ? 'bad' : ''

export const categories = {
  apartment: 'Apartamento',
  house: 'Casa',
  penthouse: 'Cobertura',
  land: 'Terreno',
  store: 'Loja',
  office: 'Sala',
  warehouse: 'Barracão',
  building: 'Prédio',
  'commercial house': 'Casa comercial',
  garage: 'Garagem',
  other: 'Outro'
}

export const precisions = { exact: 'Exata', street: 'Pela rua', neighborhood: 'Só bairro' }
export const purposes = { sale: 'Venda', rent: 'Aluguel' }

export const summary = p => [
  p.area && `${int(p.area)} m²`,
  p.bedrooms && `${p.bedrooms} qto`,
  p.suites && `${p.suites} suíte`,
  p.parking && `${p.parking} vaga`
].filter(Boolean).join(' · ')

export const escape = text => String(text ?? '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`)
