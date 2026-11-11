import json
from pathlib import Path
from urllib.parse import urlencode

import psycopg

LONDRINA = (-23.60, -51.40, -23.15, -50.90)


def inside(lat: float, lon: float) -> bool:
    south, west, north, east = LONDRINA
    return south <= lat <= north and west <= lon <= east


def set_point(conn: psycopg.Connection, listing_id: int, lat: float, lon: float, precision: str, origin: str):
    conn.execute(
        'update listing set geom = st_setsrid(st_makepoint(%s, %s), 4326), geo_precision = %s, geo_source = %s '
        'where id = %s',
        [lon, lat, precision, origin, listing_id],
    )


NOMINATIM = 'https://nominatim.openstreetmap.org/search'
MISSING = """
select distinct on (l.id) s.address, s.neighborhood from listing l join snapshot s on s.listing_id = l.id
where l.geom is null or l.geo_precision = 'neighborhood' order by l.id, s.observed_at desc
"""


def lookup(client, params: dict) -> list | None:
    response = client.fetch(f'{NOMINATIM}?{urlencode({**params, "format": "json", "limit": 1, "countrycodes": "br"})}')
    hits = response.json() if response.status_code == 200 else []
    return [float(hits[0]['lat']), float(hits[0]['lon']), hits[0]['display_name']] if hits else None


def geocode(conn: psycopg.Connection, client, path: Path, city: str, state: str, canonical) -> dict[str, int]:
    data = json.loads(path.read_text()) if path.exists() else {}
    streets = data.setdefault('streets', {})
    rows = conn.execute(MISSING).fetchall()
    neighborhoods = {canonical(n) for _, n in rows if n} - streets.keys()
    addresses = {a for a, _ in rows if a} - streets.keys()
    counts = {'neighborhoods': 0, 'streets': 0}
    for name in sorted(neighborhoods):
        hit = lookup(client, {'q': f'{name}, {city}, {state}'})
        if hit and inside(*hit[:2]):
            streets[name] = hit
            counts['neighborhoods'] += 1
    for address in sorted(addresses):
        hit = lookup(client, {'street': address, 'city': city, 'state': state})
        if hit and inside(*hit[:2]):
            streets[address] = hit
            counts['streets'] += 1
    path.write_text(json.dumps(data, ensure_ascii=False))
    return counts


def locate(conn: psycopg.Connection, path: Path, canonical=lambda name: name) -> dict[str, int]:
    data = json.loads(path.read_text())
    counts = {'exact': 0, 'street': 0, 'neighborhood': 0}
    for source_id, points in data.get('exact', {}).items():
        for code, point in points.items():
            row = conn.execute(
                'select id from listing where source_id = %s and external_id = %s', [source_id, code]
            ).fetchone()
            if row and point and inside(*point):
                set_point(conn, row[0], point[0], point[1], 'exact', 'listing page')
                counts['exact'] += 1
    streets = data.get('streets', {})
    rows = conn.execute(
        'select distinct on (l.id) l.id, s.address, s.neighborhood from listing l '
        'join snapshot s on s.listing_id = l.id where l.geom is null or l.geo_precision = %s '
        'order by l.id, s.observed_at desc',
        ['neighborhood'],
    ).fetchall()
    for listing_id, address, neighborhood in rows:
        if address in streets:
            lat, lon = streets[address][:2]
            set_point(conn, listing_id, lat, lon, 'street', 'nominatim street')
            counts['street'] += 1
        elif canonical(neighborhood) in streets:
            lat, lon = streets[canonical(neighborhood)][:2]
            set_point(conn, listing_id, lat, lon, 'neighborhood', 'nominatim neighborhood')
            counts['neighborhood'] += 1
    conn.commit()
    return counts
