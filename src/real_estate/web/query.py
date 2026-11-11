import math
from collections import Counter
from dataclasses import dataclass, field

import psycopg

from real_estate.analysis import category, distance_km
from real_estate.listing import slug

CURRENT = """
select distinct on (s.listing_id, s.purpose)
  l.id, l.source_id as source, src.name as agency, l.external_id as code, l.url, s.purpose::text as purpose, s.type,
  s.price::float as price, coalesce(s.area_useful, s.area_total)::float as area, s.bedrooms, s.suites, s.bathrooms,
  s.parking, s.address, s.neighborhood, st_y(l.geom) as lat, st_x(l.geom) as lon, l.geo_precision::text as precision,
  s.observed_at, v.model_price::float as model_price, v.gap_pct::float as gap_pct,
  coalesce(v.outlier, false) as outlier, coalesce(v.duplicate, false) as duplicate,
  f.listing_id is not null as favorite, f.note
from snapshot s
join listing l on l.id = s.listing_id
join source src on src.id = l.source_id
left join valuation v on v.listing_id = s.listing_id and v.purpose = s.purpose
left join favorite f on f.listing_id = l.id
where l.active
order by s.listing_id, s.purpose, s.observed_at desc
"""


@dataclass
class Filters:
    purpose: str | None = None
    categories: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    neighborhoods: list[str] = field(default_factory=list)
    precisions: list[str] = field(default_factory=list)
    price: tuple[float | None, float | None] = (None, None)
    area: tuple[float | None, float | None] = (None, None)
    price_m2: tuple[float | None, float | None] = (None, None)
    gap: tuple[float | None, float | None] = (None, None)
    bedrooms: int | None = None
    suites: int | None = None
    parking: int | None = None
    text: str = ''
    polygon: list[tuple[float, float]] = field(default_factory=list)
    favorites: bool = False
    clean: bool = False


def rows(conn: psycopg.Connection, canonical) -> list[dict]:
    cursor = conn.execute(CURRENT)
    names = [c.name for c in cursor.description]
    result = []
    for values in cursor.fetchall():
        row = dict(zip(names, values, strict=True))
        row['category'] = category(row['type'])
        row['neighborhood'] = canonical(row['neighborhood'])
        row['price_m2'] = row['price'] / row['area'] if row['area'] else None
        row['observed_at'] = row['observed_at'].isoformat()
        result.append(row)
    names: dict[str, Counter] = {}
    for row in result:
        if row['neighborhood']:
            names.setdefault(slug(row['neighborhood']), Counter())[row['neighborhood']] += 1
    display = {key: max(c, key=lambda n: (not n.isascii(), c[n])) for key, c in names.items()}
    for row in result:
        if row['neighborhood']:
            row['neighborhood'] = display[slug(row['neighborhood'])]
    return result


def between(value, bounds) -> bool:
    low, high = bounds
    if low is None and high is None:
        return True
    if value is None:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def inside(lon: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def matches(row: dict, f: Filters) -> bool:
    checks = [
        not f.purpose or row['purpose'] == f.purpose,
        not f.categories or row['category'] in f.categories,
        not f.sources or row['source'] in f.sources,
        not f.neighborhoods or row['neighborhood'] in f.neighborhoods,
        not f.precisions or row['precision'] in f.precisions,
        between(row['price'], f.price),
        between(row['area'], f.area),
        between(row['price_m2'], f.price_m2),
        between(row['gap_pct'], f.gap),
        f.bedrooms is None or (row['bedrooms'] or 0) >= f.bedrooms,
        f.suites is None or (row['suites'] or 0) >= f.suites,
        f.parking is None or (row['parking'] or 0) >= f.parking,
        not f.favorites or row['favorite'],
        not f.clean or not (row['outlier'] or row['duplicate']),
        not f.text or f.text.lower() in ' '.join(str(row[k] or '') for k in ('address', 'code', 'type')).lower(),
        not f.polygon or (row['lat'] is not None and inside(row['lon'], row['lat'], f.polygon)),
    ]
    return all(checks)


def feature(row: dict) -> dict:
    geometry = None if row['lat'] is None else {'type': 'Point', 'coordinates': [row['lon'], row['lat']]}
    properties = {k: v for k, v in row.items() if k not in ('lat', 'lon')}
    properties['key'] = f'{row["id"]}:{row["purpose"]}'
    return {'type': 'Feature', 'geometry': geometry, 'properties': properties}


def estimate(terms: dict[str, float], kind: str, area: float, counts: dict[str, float], lat=None, lon=None) -> float:
    log = terms['intercept'] + terms['log_area'] * math.log(area) + terms.get(f'cat_{kind}', 0)
    log += sum(terms.get(name, 0) * value for name, value in counts.items())
    if lat is not None and lon is not None:
        log += terms['distance_km'] * distance_km(lat, lon)
    return math.exp(log) * terms['smearing']
