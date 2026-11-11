import json
from types import SimpleNamespace

from real_estate.adapters import casasoft, keyspot, kurole
from real_estate.crawl import paginate
from real_estate.listing import Offer

PEREZ = 'https://www.imobiliariaperez.com.br'
SANTAMERICA = 'https://www.santamerica.com.br'
VENEZA = 'https://www.veneza.com.br'


def keyspot_page(total: int, codes: list[str]) -> str:
    graph = {'@graph': [{'@type': 'CollectionPage', 'mainEntity': {'@type': 'ItemList', 'numberOfItems': total}}]}
    cards = ''.join(
        f'<div><a href="/imovel/apartamento-a-venda-3-quartos-centro-londrina-pr-cod-{code}"></a>'
        f'<div><span>Cód. <!-- -->{code}</span><span>Centro, Londrina/PR</span><h2>Apartamento no Centro</h2>'
        '<span>R$ 900.000</span><span><b>Locação</b> R$ 4.000<!-- -->/mês</span>'
        '<span>3 Quartos</span><span>1 Suíte</span><span>2 Banheiros</span><span>2 Vagas</span>'
        '<span>86 m² Privativos</span><span>137 m² Total</span><span>Condomínio R$ 800</span></div></div>'
        for code in codes
    )
    return (
        f'<html><head><script type="application/ld+json">{json.dumps(graph)}</script></head><body>{cards}</body></html>'
    )


def test_keyspot_card_reads_both_offers_and_areas():
    total, (item,) = keyspot.parse_search(keyspot_page(194, ['11725']), f'{PEREZ}/venda/pr/londrina/centro')
    assert total == 194
    assert (item.external_id, item.type, item.neighborhood) == ('11725', 'apartamento', 'Centro')
    assert (item.area_useful, item.area_total, item.bedrooms, item.suites, item.bathrooms, item.parking) == (
        86,
        137,
        3,
        1,
        2,
        2,
    )
    assert item.offers == [Offer('sale', 900000), Offer('rent', 4000)]


KUROLE = """<html><head><title>115 imóveis Centro Apartamento Padrão em Londrina, PR para venda</title></head><body>
<div class="card card-imo"><div class="cod-imovel"><div>Cód. <strong>56006</strong></div></div>
<a href="/comprar/Londrina/Apartamento/Padrao/Centro/56006" class="carousel-cell"></a>
<div class="card-valores"><div><div><small><del>R$ 350.000,00</del></small></div>
R$ 2.000,00 L R$ 319.000,00 V</div></div>
<div class="card-bairro-cidade-texto"> Centro - Londrina/PR </div>
<div class="imo-dad-compl"><div class="dorm-ico" title="2 Dormitórios"></div>
<div class="banh-ico" title="1 Banheiro"></div>
<div class="gar-ico" title="1 Garagem, 1 coberta"></div>
<div class="a-util-ico"><span>51.25 m²</span> A. Útil</div></div>
</div></body></html>"""


def test_kurole_card_skips_old_price():
    total, (item,) = kurole.parse_search(KUROLE, f'{SANTAMERICA}/comprar/Londrina/Apartamento/Padrao/Centro')
    assert total == 115
    assert (item.external_id, item.type, item.neighborhood) == ('56006', 'Apartamento/Padrao', 'Centro')
    assert (item.bedrooms, item.suites, item.bathrooms, item.parking, item.area_useful) == (2, None, 1, 1, 51.25)
    assert item.offers == [Offer('rent', 2000), Offer('sale', 319000)]


def test_kurole_categories_follow_scope():
    xml = ''.join(
        f'<loc>{SANTAMERICA}{path}</loc>'
        for path in (
            '/comprar/Londrina/Apartamento/Padrao/Centro',
            '/alugar/Londrina/Comercial/Sala/Centro',
            '/comprar/Cambe/Apartamento/Padrao/Centro',
            '/comprar/Londrina/Apartamento/Padrao/Centro/56006',
        )
    )
    assert kurole.categories(xml, 'Londrina', 'Centro') == [
        f'{SANTAMERICA}/comprar/Londrina/Apartamento/Padrao/Centro',
        f'{SANTAMERICA}/alugar/Londrina/Comercial/Sala/Centro',
    ]


def test_casasoft_reads_listing_from_url():
    xml = ''.join(
        f'<url><loc>{VENEZA}/imovel/{slug}</loc></url>'
        for slug in (
            'apartamento-3-quartos-centro-londrina-1-vaga-150m2-venda-rs-480000/5770/04580.015',
            'salao-loja-centro-londrina-580m2-venda-rs-8000000/5770/55724.002',
            'casa-comercial-centro-londrina-locacao/5770/01111.001',
            'apartamento-2-quartos-lima-azevedo-londrina-67m2-venda-rs-289000/5770/06343.011',
        )
    )
    apartment, store, no_price = casasoft.parse_sitemap(xml, 'Londrina', 'Centro')
    assert (apartment.external_id, apartment.type, apartment.bedrooms, apartment.parking) == (
        '04580.015',
        'apartamento',
        3,
        1,
    )
    assert (apartment.area_useful, apartment.offers) == (150, [Offer('sale', 480000)])
    assert (store.type, store.bedrooms, store.area_useful) == ('salao loja', None, 580)
    assert no_price.offers == []


def test_paginate_stops_at_total():
    requested = []

    class Fake:
        def get(self, url):
            requested.append(url)
            codes = [str(len(requested) * 10 + i) for i in range(2)]
            return SimpleNamespace(text=keyspot_page(3, codes), url=url, status_code=200)

    pages = list(paginate(Fake(), f'{PEREZ}/venda', lambda u, n: f'{u}?pagina={n}', keyspot.parse_search))
    assert requested == [f'{PEREZ}/venda', f'{PEREZ}/venda?pagina=2']
    assert sum(len(p[3]) for p in pages) == 4


def test_kurole_categories_city_wide():
    xml = ''.join(
        f'<loc>{SANTAMERICA}{path}</loc>'
        for path in (
            '/comprar/Londrina/Apartamento',
            '/alugar/Londrina/Comercial',
            '/comprar/Londrina/Apartamento/Padrao/Centro',
            '/comprar/Cambe/Casa',
        )
    )
    assert kurole.categories(xml, 'Londrina', None) == [
        f'{SANTAMERICA}/comprar/Londrina/Apartamento',
        f'{SANTAMERICA}/alugar/Londrina/Comercial',
    ]


def test_casasoft_city_wide_reads_neighborhood():
    xml = ''.join(
        f'<url><loc>{VENEZA}/imovel/{slug}</loc></url>'
        for slug in (
            'casa-residencial-3-quartos-gleba-fazenda-palhano-londrina-2-vagas-240m2-venda-rs-950000/5770/01.001',
            'salao-loja-jardim-higienopolis-londrina-80m2-locacao-rs-3500/5770/02.001',
            'apartamento-2-quartos-chacara-manella-cambe-1-vaga-50m2-venda-rs-200000/5770/03.001',
        )
    )
    house, store = casasoft.parse_sitemap(xml, 'Londrina', None)
    assert (house.type, house.neighborhood, house.bedrooms, house.parking) == (
        'casa residencial',
        'Gleba Fazenda Palhano',
        3,
        2,
    )
    assert (store.type, store.neighborhood, store.offers) == (
        'salao loja',
        'Jardim Higienopolis',
        [Offer('rent', 3500)],
    )


def test_keyspot_city_url():
    requested = []

    class Fake:
        def get(self, url):
            requested.append(url)
            return SimpleNamespace(text='', url=url, status_code=404)

    list(keyspot.collect(Fake(), PEREZ, 'Londrina', 'PR', None))
    assert requested == [f'{PEREZ}/venda/pr/londrina', f'{PEREZ}/alugar/pr/londrina']
