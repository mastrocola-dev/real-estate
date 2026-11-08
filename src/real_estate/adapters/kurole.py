import re
from collections.abc import Iterator
from urllib.parse import urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from real_estate.crawl import Page, paginate
from real_estate.http import Client
from real_estate.listing import Listing, Offer, area, money

PURPOSES = {'V': 'sale', 'L': 'rent'}


def text(node, selector: str) -> str:
    found = node.css_first(selector)
    return ' '.join(found.text(separator=' ').split()) if found else ''


def number(node, selector: str) -> int | None:
    found = node.css_first(selector)
    match = re.search(r'\d+', found.attributes.get('title', '') if found else '')
    return int(match.group()) if match else None


def offers(card) -> list[Offer]:
    values = card.css_first('.card-valores')
    if not values:
        return []
    for old in values.css('del'):
        old.decompose()
    flat = ' '.join(values.text(separator=' ').split())
    return [
        Offer(PURPOSES[m.group(2)], money(f'R$ {m.group(1)}')) for m in re.finditer(r'R\$\s*([\d.,]+)\s*([VL])\b', flat)
    ]


def parse_search(html: str, url: str) -> tuple[int | None, list[Listing]]:
    tree = HTMLParser(html)
    title = tree.css_first('title')
    found = re.match(r'\s*(\d+)\s+im', title.text()) if title else None
    listings = []
    for card in tree.css('div.card.card-imo'):
        link = card.css_first('a[href*="/comprar/"], a[href*="/alugar/"]')
        code = re.search(r'\d+', text(card, '.cod-imovel'))
        if not link or not code:
            continue
        segments = urlparse(urljoin(url, link.attributes['href'])).path.strip('/').split('/')
        listings.append(
            Listing(
                external_id=code.group(),
                url=urljoin(url, link.attributes['href']),
                type='/'.join(segments[2:4]) or None,
                neighborhood=text(card, '.card-bairro-cidade-texto').split(' - ')[0] or None,
                area_useful=area(text(card, '.a-util-ico')),
                area_total=area(text(card, '.a-total-ico')),
                bedrooms=number(card, '.dorm-ico'),
                suites=number(card, '.suites-ico'),
                bathrooms=number(card, '.banh-ico'),
                parking=number(card, '.gar-ico'),
                offers=offers(card),
            )
        )
    return (int(found.group(1)) if found else None), listings


def categories(xml: str, city: str, neighborhood: str) -> list[str]:
    hood = re.escape(neighborhood.replace(' ', '-'))
    pattern = rf'<loc>\s*([^<\s]+/(?:comprar|alugar)/{re.escape(city)}/[^/<]+/[^/<]+/{hood})\s*</loc>'
    return list(dict.fromkeys(re.findall(pattern, xml)))


def collect(client: Client, base_url: str, city: str, state: str, neighborhood: str) -> Iterator[Page]:
    sitemap = client.get(urljoin(base_url, '/xml/sitemap/sitemap.xml'))
    yield str(sitemap.url), sitemap.status_code, sitemap.text, []
    for url in categories(sitemap.text, city, neighborhood):
        yield from paginate(client, url, lambda u, n: f'{u}?pag={n}', parse_search)
