import json

from real_estate.adapters.kenlo import parse_search, search_urls
from real_estate.listing import Offer

BASE = 'https://www.example.com.br'
ITEMS = {
    '@type': 'ItemList',
    'itemListElement': [
        {
            'item': {
                'name': 'Sala de 56 m² na Mato Grosso - Centro - Londrina - PR, à venda por R$ 690.000',
                'url': f'{BASE}/imovel/sala-londrina-56-m/SA0616-INIC',
                'offers': [
                    {
                        'businessFunction': 'http://purl.org/goodrelations/v1#Sell',
                        'price': 690000,
                        'availability': 'https://schema.org/InStock',
                    },
                    {
                        'businessFunction': 'http://purl.org/goodrelations/v1#LeaseOut',
                        'price': 2550,
                        'availability': 'https://schema.org/OutOfStock',
                    },
                ],
            }
        }
    ],
}


def card(href: str, title: str, heading: str, features: str, values: list[tuple[str, str]]) -> str:
    boxes = ''.join(
        f'<div class="card-with-buttons__value-container"><p class="card-with-buttons__value-title">{t}</p>'
        f'<p class="card-with-buttons__value">{v}</p></div>'
        for t, v in values
    )
    return (
        f'<a class="card-with-buttons borderHover" href="{href}"><div class="card-with-buttons__footer">'
        f'<div><span class="card-with-buttons__code">X</span><h2 class="card-with-buttons__title">{title}</h2>'
        f'<h3 class="card-with-buttons__heading">{heading}</h3><ul>{features}</ul></div>'
        f'<div class="card-with-buttons__container-footer">{boxes}</div></div></a>'
    )


HTML = (
    '<html><head><title>142 Imóveis à venda Centro, Londrina - PR</title>'
    f'<script type="application/ld+json">{json.dumps(ITEMS)}</script></head><body>'
    + card(
        '/imovel/sala-londrina-56-m/SA0616-INIC?from=sale',
        'Sala',
        'Centro - Londrina - PR Metropolitan Med Center',
        '<li>56.15 m²</li><li>1 Banheiro</li><li>1 Vaga</li>',
        [('Venda', 'R$ 690.000'), ('Aluguel', 'R$ 2.550/mês')],
    )
    + card(
        '/imovel/apartamento-londrina-4-quartos-160-m/AP6142-INIC?from=sale',
        'Apartamento',
        'Centro - Londrina - PR',
        '<li>1.160 m²</li><li>4 Quartos</li><li>2 Suítes</li><li>3 Banheiros</li><li>1 Vaga</li>',
        [('Venda', 'R$ 472.000'), ('Aluguel', 'R$ 2.300/mês')],
    )
    + '<a class="card_split_vertically" href="/imovel/apartamento-londrina-2-quartos-46-m/AP4364-MONA?from=sale">'
    '<p class="card_split_vertically__code">AP4364-MONA</p><p class="card_split_vertically__type">Apartamento</p>'
    '<h2 class="card_split_vertically__location">Centro - Londrina - PR</h2><ul class="card_split_vertically__specs">'
    '<li>45.95 m²</li><li>2 Quartos</li><li>1 Banheiro</li><li>1 Vaga</li></ul>'
    '<div class="card_split_vertically__value-container"><p class="card_split_vertically__value-title">Venda</p>'
    '<p class="card_split_vertically__value">R$ 295.000</p></div></a>'
    + '<a href="/imovel/sem-codigo/X">ignored</a>'
    + '</body></html>'
)


def test_parses_cards_with_json_ld_offers():
    total, (sala, apartamento, _) = parse_search(HTML, f'{BASE}/imoveis/a-venda/londrina/centro')
    assert total == 142
    assert sala.external_id == 'SA0616-INIC'
    assert sala.url == f'{BASE}/imovel/sala-londrina-56-m/SA0616-INIC'
    assert (sala.type, sala.neighborhood, sala.address) == ('Sala', 'Centro', 'Mato Grosso')
    assert (sala.area_useful, sala.bathrooms, sala.parking, sala.bedrooms) == (56.15, 1, 1, None)
    assert sala.offers == [Offer('sale', 690000), Offer('rent', 2550, False)]
    assert sala.active


def test_falls_back_to_card_values_and_reads_thousands_area():
    _, (_, apartamento, _) = parse_search(HTML, f'{BASE}/imoveis/a-venda/londrina/centro')
    assert apartamento.address is None
    assert (apartamento.area_useful, apartamento.bedrooms, apartamento.suites) == (1160, 4, 2)
    assert apartamento.offers == [Offer('sale', 472000), Offer('rent', 2300)]


def test_reads_split_vertically_template():
    _, (*_, split) = parse_search(HTML, f'{BASE}/imoveis/a-venda/londrina/centro')
    assert (split.external_id, split.type, split.neighborhood) == ('AP4364-MONA', 'Apartamento', 'Centro')
    assert (split.area_useful, split.bedrooms, split.bathrooms, split.parking) == (45.95, 2, 1, 1)
    assert split.offers == [Offer('sale', 295000)]


def test_search_urls_cover_sale_and_rent():
    assert search_urls(BASE, 'Londrina', 'Centro') == [
        f'{BASE}/imoveis/a-venda/londrina/centro',
        f'{BASE}/imoveis/para-alugar/londrina/centro',
    ]
