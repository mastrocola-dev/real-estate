import json
from collections.abc import Iterator
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

from real_estate.crawl import Page
from real_estate.http import Client
from real_estate.listing import Listing, Offer, slug

PURPOSES = {'a-venda': 'sale', 'para-alugar': 'rent'}
DROP = ('fotos', 'nearbyInfo', 'bairroInfo', 'comodidades', 'unavailableComodidades', 'imobiliaria', 'imv_obs')


def page_props(html: str) -> dict:
    node = LexborHTMLParser(html).css_first('script#__NEXT_DATA__')
    return json.loads(node.text())['props']['pageProps'] if node else {}


def codes(html: str) -> list[str]:
    return [item['imv_cod_gaia'] for item in page_props(html).get('locations', []) if item.get('imv_cod_gaia')]


def property_data(html: str) -> dict | None:
    data = page_props(html).get('imovel')
    return {k: v for k, v in data.items() if k not in DROP} if data else None


def positive(value) -> float | None:
    return float(value) if value else None


def to_listing(data: dict) -> Listing:
    published = data.get('imv_ativo', True) and (data.get('status_imovel') or {}).get('publicado', True)
    hidden = data.get('imv_ocultar_preco')
    offers = [
        Offer(purpose, float(data[key]), bool(published))
        for purpose, key in (('sale', 'imv_preco_venda'), ('rent', 'imv_preco_locacao'))
        if data.get(key) and not hidden
    ]
    lat = data.get('imv_latitude') or (data.get('imv_location') or {}).get('lat')
    lon = data.get('imv_longitude') or (data.get('imv_location') or {}).get('lng')
    return Listing(
        external_id=data['imv_cod_gaia'],
        url=data.get('url_amiga') or '',
        type=(data.get('tipo_imovel') or {}).get('timv_nome'),
        neighborhood=data.get('imv_bairro'),
        address=data.get('imv_endereco'),
        area_useful=positive(data.get('imv_area_util')),
        area_total=positive(data.get('imv_area_total') or data.get('imv_area_terreno')),
        bedrooms=data.get('imv_qtd_dorm'),
        suites=data.get('imv_qtd_suite'),
        bathrooms=data.get('imv_qtd_banheiros'),
        parking=data.get('imv_qtd_vagas'),
        condo_fee=positive(data.get('imv_preco_cond')),
        iptu=positive(data.get('imv_preco_iptu')),
        point=(float(lat), float(lon)) if lat and lon else None,
        offers=offers,
    )


def parse_detail(text: str, url: str, city: str) -> tuple[None, list[Listing]]:
    data = json.loads(text)
    if slug(data.get('imv_cidade') or '') != slug(city):
        return None, []
    return None, [to_listing(data)]


def search_url(base_url: str, purpose: str, city: str, state: str, neighborhood: str | None) -> str:
    place = '-'.join(slug(p) for p in (neighborhood, city, state) if p)
    return urljoin(base_url, f'/imoveis/{purpose}/{place}')


def collect(client: Client, base_url: str, city: str, state: str, neighborhood: str | None) -> Iterator[Page]:
    found: dict[str, None] = {}
    for purpose in PURPOSES:
        response = client.get(search_url(base_url, purpose, city, state, neighborhood))
        listed = codes(response.text) if response.status_code == 200 else []
        yield str(response.url), response.status_code, json.dumps(listed), []
        found.update(dict.fromkeys(listed))
    for code in found:
        response = client.get(urljoin(base_url, f'/imovel/imovel/negocio/{slug(city)}/{slug(state)}/bairro/{code}'))
        data = property_data(response.text) if response.status_code == 200 else None
        if data is None:
            yield str(response.url), response.status_code, '', []
            continue
        body = json.dumps(data, ensure_ascii=False)
        yield str(response.url), response.status_code, body, parse_detail(body, str(response.url), city)[1]
