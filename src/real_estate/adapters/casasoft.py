import re
from collections.abc import Iterator
from urllib.parse import urljoin

from real_estate.crawl import Page
from real_estate.http import Client
from real_estate.listing import Listing, Offer, slug

PURPOSES = {'venda': 'sale', 'locacao': 'rent'}


TYPES = r'casa-residencial|casa-comercial|chacara-imovel-rural|salao-loja|predio-comercial|[a-z]+'


def pattern(city: str, neighborhood: str | None) -> re.Pattern:
    hood = re.escape(slug(neighborhood)) if neighborhood else '[a-z0-9-]+?'
    return re.compile(
        rf'/imovel/(?P<type>{TYPES})(?:-(?P<bedrooms>\d+)-quartos?)?'
        rf'-(?P<hood>{hood})-{re.escape(slug(city))}'
        r'(?:-(?P<parking>\d+)-vagas?)?(?:-(?P<area>\d+)m2)?-(?P<purpose>venda|locacao)(?:-rs-(?P<price>\d+))?'
        r'/\d+/(?P<code>[\d.]+)$'
    )


def parse_sitemap(xml: str, city: str, neighborhood: str | None) -> list[Listing]:
    match_url = pattern(city, neighborhood)
    listings = []
    for url in re.findall(r'<loc>\s*(\S+?)\s*</loc>', xml):
        m = match_url.search(url)
        if not m:
            continue
        listings.append(
            Listing(
                external_id=m['code'],
                url=url,
                type=m['type'].replace('-', ' '),
                neighborhood=neighborhood or m['hood'].replace('-', ' ').title(),
                area_useful=float(m['area']) if m['area'] else None,
                bedrooms=int(m['bedrooms']) if m['bedrooms'] else None,
                parking=int(m['parking']) if m['parking'] else None,
                offers=[Offer(PURPOSES[m['purpose']], float(m['price']))] if m['price'] else [],
            )
        )
    return listings


def collect(client: Client, base_url: str, city: str, state: str, neighborhood: str | None) -> Iterator[Page]:
    for transaction in ('v', 'l'):
        response = client.get(urljoin(base_url, f'/sitemap-dynamic.xml?page=imovel&transaction={transaction}'))
        yield str(response.url), response.status_code, response.text, parse_sitemap(response.text, city, neighborhood)
