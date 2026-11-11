import json
import re
from collections.abc import Iterator
from urllib.parse import urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from real_estate.crawl import Page, paginate
from real_estate.http import Client
from real_estate.listing import Listing, Offer, area, count, money, slug

PRICE = re.compile(r'(Condom[íi]nio|IPTU)?\s*R\$\s*([\d.]+(?:,\d{2})?)(\s*/\s*m[êe]s)?', re.IGNORECASE)


def total(tree: HTMLParser) -> int | None:
    for node in tree.css('script[type="application/ld+json"]'):
        for item in json.loads(node.text()).get('@graph', []):
            entity = item.get('mainEntity', {})
            if entity.get('@type') == 'ItemList':
                return entity.get('numberOfItems')
    return None


def offers(text: str) -> list[Offer]:
    return [
        Offer('rent' if m.group(3) else 'sale', money(f'R$ {m.group(2)}'))
        for m in PRICE.finditer(text)
        if not m.group(1)
    ]


def measure(text: str, label: str) -> float | None:
    match = re.search(rf'([\d.,]+\s*m²)\s*{label}', text)
    return area(match.group(1)) if match else None


def parse_search(html: str, url: str) -> tuple[int | None, list[Listing]]:
    tree = HTMLParser(html)
    listings = {}
    for anchor in tree.css('a[href^="/imovel/"]'):
        path = urlparse(anchor.attributes['href']).path
        text = ' '.join(anchor.parent.text(separator=' ').split())
        code = re.search(r'-cod-(\w+)$', path)
        if not code or 'Cód.' not in text or code.group(1) in listings:
            continue
        kind = re.match(r'/imovel/(.+?)-(?:a-venda|para-alugar)', path)
        place = re.search(r'Cód\.\s*\w+\s+(.+?),\s*[^,]+?/[A-Z]{2}\b', text)
        listings[code.group(1)] = Listing(
            external_id=code.group(1),
            url=urljoin(url, path),
            type=kind.group(1).replace('-', ' ') if kind else None,
            neighborhood=place.group(1) if place else None,
            area_useful=measure(text, 'Privativ'),
            area_total=measure(text, 'Total'),
            bedrooms=count(text, 'quartos?'),
            suites=count(text, 'suítes?'),
            bathrooms=count(text, 'banheiros?'),
            parking=count(text, 'vagas?'),
            offers=offers(text),
        )
    return total(tree), list(listings.values())


def collect(client: Client, base_url: str, city: str, state: str, neighborhood: str | None) -> Iterator[Page]:
    for purpose in ('venda', 'alugar'):
        place = '/'.join(slug(p) for p in (state, city, neighborhood) if p)
        url = urljoin(base_url, f'/{purpose}/{place}')
        yield from paginate(client, url, lambda u, n: f'{u}?pagina={n}', parse_search)
