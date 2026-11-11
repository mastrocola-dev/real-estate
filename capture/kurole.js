const out = []
for (const [path, total] of CATS) {
  for (let page = 1; page <= Math.ceil(total / 27); page++) {
    const url = location.origin + path + (page > 1 ? `?pag=${page}` : '')
    const doc = new DOMParser().parseFromString(await fetch(url).then(r => r.text()), 'text/html')
    const keep = ['.cod-imovel', '.card-valores', '.card-titulo', '.card-bairro-cidade-texto', '.imo-dad-compl']
    const cards = [...doc.querySelectorAll('div.card.card-imo')].map(c => {
      const link = c.querySelector('a[href*="/comprar/"], a[href*="/alugar/"]')
      return '<div class="card card-imo">' + `<a href="${link?.getAttribute('href') ?? ''}"></a>` + keep.map(s => c.querySelector(s)?.outerHTML ?? '').join('') + '</div>'
    }).join('')
    out.push({ url, captured_at: new Date().toISOString(), html: '<html><head><title>' + doc.title + '</title></head><body>' + cards + '</body></html>' })
    await new Promise(r => setTimeout(r, 2000))
  }
}
out
