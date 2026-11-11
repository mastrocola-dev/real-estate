import json
from types import SimpleNamespace

from real_estate.adapters import arbo
from real_estate.listing import Offer

CRV = 'https://www.crvimobiliaria.com.br'
DETAIL = {
    'imv_location': {'lng': -51.2069049, 'lat': -23.3490941},
    'imv_ativo': True,
    'imv_cod_gaia': 'SO0383_CRV',
    'imv_preco_venda': 1500000,
    'imv_preco_locacao': 9000,
    'imv_preco_cond': 2000,
    'imv_preco_iptu': None,
    'imv_area_util': 468,
    'imv_area_total': 468,
    'imv_qtd_dorm': 4,
    'imv_qtd_suite': 4,
    'imv_qtd_vagas': 2,
    'imv_qtd_banheiros': 5,
    'imv_cidade': 'Londrina',
    'imv_bairro': 'Esperança',
    'imv_endereco': 'Avenida Gil de Abreu Souza',
    'imv_latitude': -23.3490941,
    'imv_longitude': -51.2069049,
    'imv_ocultar_preco': False,
    'url_amiga': f'{CRV}/imovel/sobrado/locacao/londrina/pr/esperanca/SO0383_CRV',
    'tipo_imovel': {'timv_nome': 'Sobrado'},
    'status_imovel': {'publicado': True},
    'fotos': [{'url': 'x'}],
}


def page(props: dict) -> str:
    data = json.dumps({'props': {'pageProps': props}})
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{data}</script></body></html>'


def test_detail_becomes_listing():
    _, (item,) = arbo.parse_detail(json.dumps(arbo.property_data(page({'imovel': DETAIL}))), '', 'Londrina')
    assert (item.external_id, item.type, item.neighborhood, item.address) == (
        'SO0383_CRV',
        'Sobrado',
        'Esperança',
        'Avenida Gil de Abreu Souza',
    )
    assert (item.area_useful, item.bedrooms, item.suites, item.parking, item.condo_fee, item.iptu) == (
        468,
        4,
        4,
        2,
        2000,
        None,
    )
    assert item.point == (-23.3490941, -51.2069049)
    assert item.offers == [Offer('sale', 1500000), Offer('rent', 9000)]


def test_other_cities_are_skipped():
    assert arbo.parse_detail(json.dumps({**DETAIL, 'imv_cidade': 'Cambé'}), '', 'Londrina') == (None, [])


def test_collect_reads_codes_then_details():
    requested = []
    search = page({'locations': [{'imv_cod_gaia': 'SO0383_CRV'}]})

    class Fake:
        def get(self, url):
            requested.append(url)
            text = page({'imovel': DETAIL}) if '/imovel/' in url else search
            return SimpleNamespace(text=text, url=url, status_code=200)

    pages = list(arbo.collect(Fake(), CRV, 'Londrina', 'PR', None))
    assert requested[:2] == [f'{CRV}/imoveis/a-venda/londrina-pr', f'{CRV}/imoveis/para-alugar/londrina-pr']
    assert len(requested) == 3
    assert 'fotos' not in pages[-1][2]
    assert pages[-1][3][0].external_id == 'SO0383_CRV'
