import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

SIGNATURES = {
    'kenlo': ['kenlo', 'ingaia', 'imobiliariaweb'],
    'jetimob': ['jetimob'],
    'vista': ['vistasoft', 'vistahost', 'vista.imobi'],
    'imobzi': ['imobzi'],
    'tecimob': ['tecimob'],
    'univen': ['univen'],
    'imoview': ['imoview'],
    'wordpress': ['wp-content'],
    'nextjs': ['/_next/'],
    'nuxt': ['/_nuxt/'],
}
PRICE = re.compile(r'R\$\s?\d{1,3}(\.\d{3})+')


@dataclass
class Fingerprint:
    url: str
    status: int
    platforms: list[str] = field(default_factory=list)
    generator: str | None = None
    hosts: list[str] = field(default_factory=list)
    prices_in_html: int = 0
    jsonld_offers: int = 0
    robots_blocks_all: bool = False
    sitemaps: list[str] = field(default_factory=list)


def platforms(html: str) -> list[str]:
    lower = html.lower()
    return [name for name, marks in SIGNATURES.items() if any(m in lower for m in marks)]


def external_hosts(tree: HTMLParser, own: str) -> list[str]:
    urls = [n.attributes.get('src') or n.attributes.get('href') for n in tree.css('script, link')]
    hosts = {urlparse(u).netloc for u in urls if u and u.startswith('http')}
    return sorted(h for h in hosts if h and not h.endswith(own))


def jsonld_offers(tree: HTMLParser) -> int:
    count = 0
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text()
        if '"offers"' in text or '"price"' in text:
            count += text.count('"price"') or 1
    return count


def robots(text: str) -> tuple[bool, list[str]]:
    blocks_all, applies, sitemaps = False, False, []
    for line in text.splitlines():
        key, _, value = line.partition(':')
        key, value = key.strip().lower(), value.strip()
        if key == 'user-agent':
            applies = value == '*'
        elif key == 'disallow' and applies and value == '/':
            blocks_all = True
        elif key == 'sitemap':
            sitemaps.append(value)
    return blocks_all, sitemaps


def fingerprint(url: str, status: int, html: str, robots_txt: str = '') -> Fingerprint:
    tree = HTMLParser(html)
    meta = tree.css_first('meta[name="generator"]')
    own = urlparse(url).netloc.removeprefix('www.')
    blocks_all, sitemaps = robots(robots_txt)
    return Fingerprint(
        url=url,
        status=status,
        platforms=platforms(html),
        generator=meta.attributes.get('content') if meta else None,
        hosts=external_hosts(tree, own),
        prices_in_html=len(PRICE.findall(html)),
        jsonld_offers=jsonld_offers(tree),
        robots_blocks_all=blocks_all,
        sitemaps=sitemaps,
    )


def report(source_id: str, prints: list[Fingerprint]) -> str:
    return json.dumps({source_id: [vars(p) for p in prints]}, ensure_ascii=False, indent=2)
