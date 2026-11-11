from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from real_estate import config, db
from real_estate.web import query

STATIC = Path(__file__).parent / 'static'
app = FastAPI(title='real-estate')
settings = config.load()


def bounds(low: float | None, high: float | None):
    return (low, high)


def split(value: str | None) -> list[str]:
    return [item for item in (value or '').split(',') if item]


def polygon(value: str | None) -> list[tuple[float, float]]:
    points = [tuple(float(n) for n in pair.split(',')) for pair in split_points(value)]
    return points if len(points) >= 3 else []


def split_points(value: str | None) -> list[str]:
    return [item for item in (value or '').split(';') if item]


@app.get('/api/meta')
def meta():
    with db.connect() as conn:
        rows = query.rows(conn, settings.canonical)
        metrics = conn.execute(
            'select purpose::text, model, rows, mape_pct::float, within_15_pct::float, r2_log::float from model_metric'
        ).fetchall()
    return {
        'city': settings.city,
        'sources': [{'id': s.id, 'name': s.name} for s in settings.sources.values()],
        'neighborhoods': sorted({r['neighborhood'] for r in rows if r['neighborhood']}),
        'categories': sorted({r['category'] for r in rows}),
        'total': len(rows),
        'metrics': [dict(zip(('purpose', 'model', 'rows', 'mape', 'within15', 'r2'), m, strict=True)) for m in metrics],
    }


@app.get('/api/listings')
def listings(
    purpose: str | None = None,
    category: str | None = None,
    source: str | None = None,
    neighborhood: str | None = None,
    precision: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    area_min: float | None = None,
    area_max: float | None = None,
    m2_min: float | None = None,
    m2_max: float | None = None,
    gap_min: float | None = None,
    gap_max: float | None = None,
    bedrooms: int | None = None,
    suites: int | None = None,
    parking: int | None = None,
    q: str = '',
    area: str | None = Query(None, alias='polygon'),
    favorites: bool = False,
    clean: bool = False,
):
    filters = query.Filters(
        purpose=purpose,
        categories=split(category),
        sources=split(source),
        neighborhoods=split(neighborhood),
        precisions=split(precision),
        price=bounds(price_min, price_max),
        area=bounds(area_min, area_max),
        price_m2=bounds(m2_min, m2_max),
        gap=bounds(gap_min, gap_max),
        bedrooms=bedrooms,
        suites=suites,
        parking=parking,
        text=q.strip(),
        polygon=polygon(area),
        favorites=favorites,
        clean=clean,
    )
    with db.connect() as conn:
        rows = [r for r in query.rows(conn, settings.canonical) if query.matches(r, filters)]
    return {'type': 'FeatureCollection', 'features': [query.feature(r) for r in rows]}


@app.get('/api/listings/{listing_id}')
def listing(listing_id: int):
    with db.connect() as conn:
        rows = [r for r in query.rows(conn, settings.canonical) if r['id'] == listing_id]
        if not rows:
            raise HTTPException(404)
        history = conn.execute(
            'select observed_at, purpose::text, price::float from snapshot where listing_id = %s order by observed_at',
            (listing_id,),
        ).fetchall()
    return {
        'offers': rows,
        'history': [{'observed_at': t.isoformat(), 'purpose': p, 'price': v} for t, p, v in history],
    }


@app.put('/api/favorites/{listing_id}')
def favorite(listing_id: int, note: str = Body('', embed=True)):
    with db.connect() as conn:
        conn.execute(
            'insert into favorite (listing_id, note) values (%s, %s) '
            'on conflict (listing_id) do update set note = excluded.note, updated_at = now()',
            (listing_id, note),
        )
    return {'listing_id': listing_id, 'note': note}


@app.delete('/api/favorites/{listing_id}')
def unfavorite(listing_id: int):
    with db.connect() as conn:
        conn.execute('delete from favorite where listing_id = %s', (listing_id,))
    return {'listing_id': listing_id}


@app.get('/api/estimate')
def estimate(
    purpose: str,
    category: str,
    area: float = Query(gt=0),
    bedrooms: int = 0,
    suites: int = 0,
    bathrooms: int = 0,
    parking: int = 0,
    lat: float | None = None,
    lon: float | None = None,
):
    with db.connect() as conn:
        terms = dict(conn.execute('select term, value from model_term where purpose = %s', (purpose,)).fetchall())
    if not terms:
        raise HTTPException(404, 'run estate analyze first')
    counts = {'bedrooms': bedrooms, 'suites': suites, 'bathrooms': bathrooms, 'parking': parking}
    price = query.estimate(terms, category, area, counts, lat, lon)
    return {'price': round(price, 2), 'price_m2': round(price / area, 2)}


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')


app.mount('/static', StaticFiles(directory=STATIC), name='static')
