import json
import re
from urllib.parse import urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from real_estate.listing import Listing, Offer, area, count, money, purpose, slug


def search_urls(base_url: str, city: str, neighborhood: str) -> list[str]:
    path = f'{slug(city)}/{slug(neighborhood)}'
    return [
        urljoin(base_url, f'/imoveis/a-venda/{path}'),
        urljoin(base_url, f'/imoveis/para-alugar/{path}'),
    ]


def item_list(tree: HTMLParser) -> dict[str, dict]:
    for node in tree.css('script[type="application/ld+json"]'):
        data = json.loads(node.text())
        if data.get('@type') == 'ItemList':
            return {urlparse(e['item']['url']).path: e['item'] for e in data['itemListElement']}
    return {}


def text(node, selector: str) -> str:
    found = node.css_first(selector)
    return ' '.join(found.text(separator=' ').split()) if found else ''


def ld_offers(item: dict) -> list[Offer]:
    offers = item.get('offers', [])
    offers = offers if isinstance(offers, list) else [offers]
    return [
        Offer(
            purpose(o['businessFunction'].rsplit('#', 1)[-1]),
            float(o['price']),
            o.get('availability', '').endswith('InStock'),
        )
        for o in offers
        if purpose(o.get('businessFunction', '').rsplit('#', 1)[-1]) and o.get('price')
    ]


def card_offers(card) -> list[Offer]:
    offers = []
    for box in card.css('[class*="__value-container"]'):
        label = purpose(text(box, '[class$="__value-title"]'))
        price = money(text(box, '[class$="__value"]'))
        if label and price:
            offers.append(Offer(label, price))
    return offers


def street(name: str) -> str | None:
    match = re.search(r' na (.+?) - ', name)
    return match.group(1) if match else None


def parse_search(html: str, url: str) -> tuple[int | None, list[Listing]]:
    tree = HTMLParser(html)
    items = item_list(tree)
    title = tree.css_first('title')
    total = re.match(r'\s*([\d.]+)', title.text()) if title else None
    listings = []
    for card in tree.css('a[href*="/imovel/"]'):
        if not card.css_first('[class*="__code"]'):
            continue
        path = urlparse(urljoin(url, card.attributes['href'])).path
        item = items.get(path, {})
        features = ' '.join(card.text(separator=' ').split())
        heading = text(card, '[class$="__heading"], [class$="__location"]')
        listings.append(
            Listing(
                external_id=path.rstrip('/').rsplit('/', 1)[-1],
                url=urljoin(url, path),
                type=text(card, '[class$="__title"], [class$="__type"]') or None,
                neighborhood=heading.split(' - ')[0] or None,
                address=street(item.get('name', '')),
                area_useful=area(features),
                bedrooms=count(features, 'quartos?'),
                suites=count(features, 'suítes?'),
                bathrooms=count(features, 'banheiros?'),
                parking=count(features, 'vagas?'),
                offers=ld_offers(item) or card_offers(card),
            )
        )
    return (int(total.group(1).replace('.', '')) if total else None), listings
