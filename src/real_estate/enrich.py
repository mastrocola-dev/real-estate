import re

import psycopg

from real_estate.http import Client, Disallowed
from real_estate.locate import inside, set_point

PATTERNS = [
    r'data-latitude="(-?\d+\.\d+)"[^>]*?data-longitude="(-?\d+\.\d+)"',
    r'initLeafletMap\(\s*[\'"]?(?:[a-z_]+[\'"]\s*,\s*)?[\'"]?(-?\d+\.\d+)[\'"]?\s*,\s*[\'"]?(-?\d+\.\d+)',
    r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
    r'"latitude"\s*:\s*"?(-?\d+\.\d+)"?\s*,\s*"longitude"\s*:\s*"?(-?\d+\.\d+)',
]
ADDRESS = r'class="[^"]*card__address[^"]*"[^>]*>([^<]+)<'
PENDING = """
select l.id, l.url from listing l
where l.source_id = any(%s) and l.active
  and (l.geo_precision is distinct from 'exact' or (%s and l.geo_source = 'listing page'))
order by l.id limit %s
"""
FILL_ADDRESS = """
update snapshot set address = %s
where listing_id = %s and coalesce(address, '') = ''
"""


def coordinates(html: str) -> tuple[float, float] | None:
    for pattern in PATTERNS:
        for lat, lon in re.findall(pattern, html):
            if inside(float(lat), float(lon)):
                return float(lat), float(lon)
    return None


def address(html: str) -> str | None:
    match = re.search(ADDRESS, html)
    return re.split(r'\s+-\s+', re.sub(r'\s+', ' ', match.group(1)).strip())[0].strip(' -,') if match else None


def enrich(
    conn: psycopg.Connection, client: Client, sources: list[str], limit: int, redo: bool = False
) -> dict[str, int]:
    counts = {'located': 0, 'missing': 0, 'failed': 0}
    for listing_id, url in conn.execute(PENDING, (sources, redo, limit)).fetchall():
        try:
            response = client.get(url)
        except Disallowed:
            counts['failed'] += 1
            continue
        if response.status_code != 200:
            counts['failed'] += 1
            continue
        point = coordinates(response.text)
        if point:
            set_point(conn, listing_id, *point, 'exact', 'listing page')
        street = address(response.text)
        if street:
            conn.execute(FILL_ADDRESS, (street, listing_id))
        conn.commit()
        counts['located' if point else 'missing'] += 1
    return counts
