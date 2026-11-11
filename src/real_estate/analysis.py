import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

CENTER = (-23.3105, -51.1628)
CATEGORIES = [
    ('land', r'terreno|lote'),
    ('garage', r'garagem|box'),
    ('penthouse', r'cobertura'),
    ('apartment', r'apartamento|apto|kitnet|kitinete|flat|studio|duplex|loft'),
    ('store', r'loja|sal[aã]o|ponto|sobreloja'),
    ('office', r'\bsalas?\b|conjunto|consult[oó]rio|escrit[oó]rio'),
    ('warehouse', r'galp[aã]o|barrac[aã]o|dep[oó]sito'),
    ('building', r'pr[eé]dio|edif[ií]cio'),
    ('commercial house', r'casa.?comercial|im[oó]vel.?comercial|imoveis.?comerciais|comercial'),
    ('house', r'casa|sobrado|resid'),
]

LATEST = """
select distinct on (s.listing_id, s.purpose)
  l.id as listing_id, l.source_id as source, l.external_id as code, l.url, s.purpose, s.type, s.price::float as price,
  coalesce(s.area_useful, s.area_total)::float as area, s.bedrooms, s.suites, s.bathrooms, s.parking,
  s.address, s.neighborhood, st_y(l.geom) as lat, st_x(l.geom) as lon, l.geo_precision::text as precision
from snapshot s join listing l on l.id = s.listing_id
where l.active
order by s.listing_id, s.purpose, s.observed_at desc
"""


def category(kind: str | None) -> str:
    text = (kind or '').lower()
    return next((name for name, pattern in CATEGORIES if re.search(pattern, text)), 'other')


def distance_km(lat: float, lon: float) -> float:
    dy = (lat - CENTER[0]) * 111.32
    dx = (lon - CENTER[1]) * 111.32 * math.cos(math.radians(CENTER[0]))
    return math.hypot(dx, dy)


def load(conn: psycopg.Connection) -> pd.DataFrame:
    frame = pd.DataFrame(conn.execute(LATEST).fetchall(), columns=[c.name for c in conn.execute(LATEST).description])
    frame['category'] = frame['type'].map(category)
    frame['price_m2'] = frame['price'] / frame['area'].where(frame['area'] > 0)
    frame['distance_km'] = [
        distance_km(a, b) if pd.notna(a) else np.nan for a, b in zip(frame['lat'], frame['lon'], strict=True)
    ]
    return frame


def flag_outliers(frame: pd.DataFrame) -> pd.Series:
    bad = (frame['parking'] > 20) | (frame['bedrooms'] > 10) | (frame['area'] < 10) | (frame['area'] > 20000)
    for _, group in frame.dropna(subset=['price_m2']).groupby(['purpose', 'category']):
        if len(group) < 8:
            continue
        log = np.log(group['price_m2'])
        q1, q3 = log.quantile([0.25, 0.75])
        fence = 3 * (q3 - q1)
        bad.loc[group.index] |= (log < q1 - fence) | (log > q3 + fence)
    return bad


def duplicates(frame: pd.DataFrame) -> pd.Series:
    duplicate = pd.Series(False, index=frame.index)
    exact = frame[frame['precision'].isin(['exact', 'street']) & frame['area'].notna()]
    for _, group in exact.groupby(['purpose', 'category']):
        rows = group.sort_values('source').to_dict('index')
        keys = list(rows)
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                x, y = rows[a], rows[b]
                if x['source'] == y['source'] or duplicate[b]:
                    continue
                near = math.hypot((x['lat'] - y['lat']) * 111.32, (x['lon'] - y['lon']) * 102.2) < 0.25
                if near and abs(x['area'] / y['area'] - 1) < 0.03 and abs(x['price'] / y['price'] - 1) < 0.05:
                    duplicate[b] = True
    return duplicate


def summary(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for (purpose, cat), group in frame.groupby(['purpose', 'category']):
        m2 = group['price_m2'].dropna()
        rows.append(
            {
                'purpose': purpose,
                'category': cat,
                'listings': len(group),
                'with_area': len(m2),
                'median_price': round(group['price'].median()),
                'median_area': None if group['area'].isna().all() else round(group['area'].median(), 1),
                'median_price_m2': None if m2.empty else round(m2.median(), 2),
                'p25_price_m2': None if m2.empty else round(m2.quantile(0.25), 2),
                'p75_price_m2': None if m2.empty else round(m2.quantile(0.75), 2),
            }
        )
    return rows


def by_source(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for (source, purpose), group in frame.groupby(['source', 'purpose']):
        res = group[group['category'] == 'apartment']['price_m2'].dropna()
        rows.append(
            {
                'source': source,
                'purpose': purpose,
                'listings': len(group),
                'apartment_median_price_m2': None if res.empty else round(res.median(), 2),
                'with_coordinates': int(group['precision'].eq('exact').sum()),
            }
        )
    return rows


def yields(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for cat, group in frame.groupby('category'):
        sale = group[group['purpose'] == 'sale']['price_m2'].dropna()
        rent = group[group['purpose'] == 'rent']['price_m2'].dropna()
        if len(sale) >= 5 and len(rent) >= 5:
            rows.append(
                {
                    'category': cat,
                    'sale_median_m2': round(sale.median(), 2),
                    'rent_median_m2': round(rent.median(), 2),
                    'gross_yield_pct': round(rent.median() * 12 / sale.median() * 100, 2),
                }
            )
    return rows


def design(frame: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    x = pd.DataFrame(index=frame.index)
    x['intercept'] = 1.0
    x['log_area'] = np.log(frame['area'])
    for column in ['bedrooms', 'suites', 'bathrooms', 'parking']:
        x[column] = pd.to_numeric(frame[column]).fillna(0).clip(upper=6)
    x['distance_km'] = frame['distance_km'].fillna(frame['distance_km'].median()).fillna(0)
    for cat in categories[1:]:
        x[f'cat_{cat}'] = (frame['category'] == cat).astype(float)
    return x


def fit_ols(x: pd.DataFrame, y: pd.Series) -> np.ndarray:
    return np.linalg.lstsq(x.to_numpy(), y.to_numpy(), rcond=None)[0]


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    error = np.abs(predicted - actual)
    return {
        'mape_pct': round(float(np.median(error / actual) * 100), 1),
        'mean_ape_pct': round(float(np.mean(error / actual) * 100), 1),
        'within_15_pct': round(float(np.mean(error / actual <= 0.15) * 100), 1),
        'r2_log': round(
            float(
                1
                - np.sum((np.log(actual) - np.log(predicted)) ** 2)
                / np.sum((np.log(actual) - np.log(actual).mean()) ** 2)
            ),
            3,
        ),
    }


def model(frame: pd.DataFrame, purpose: str) -> tuple[dict, pd.Series]:
    data = frame[(frame['purpose'] == purpose) & frame['area'].notna() & ~frame['outlier'] & ~frame['duplicate']]
    data = data[data['category'] != 'other']
    counts = data['category'].value_counts()
    categories = [c for c in counts.index if counts[c] >= 5]
    data = data[data['category'].isin(categories)]
    categories = sorted(categories, key=lambda c: -counts[c])
    x, y = design(data, categories), np.log(data['price'])
    folds = KFold(5, shuffle=True, random_state=7)
    ols_pred, gb_pred = np.zeros(len(y)), np.zeros(len(y))
    gb_x = x.drop(columns=['intercept', 'distance_km']).assign(
        lat=data['lat'].fillna(CENTER[0]), lon=data['lon'].fillna(CENTER[1])
    )
    for train, test in folds.split(x):
        beta = fit_ols(x.iloc[train], y.iloc[train])
        ols_pred[test] = x.iloc[test].to_numpy() @ beta
        booster = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=15, random_state=7)
        booster.fit(gb_x.iloc[train], y.iloc[train])
        gb_pred[test] = booster.predict(gb_x.iloc[test])
    beta = fit_ols(x, y)
    residual = y - x.to_numpy() @ beta
    smearing = float(np.mean(np.exp(residual)))
    fitted = pd.Series(np.exp(x.to_numpy() @ beta) * smearing, index=data.index)
    result = {
        'purpose': purpose,
        'rows': len(data),
        'categories': categories,
        'baseline': categories[0],
        'coefficients': {name: round(float(b), 5) for name, b in zip(x.columns, beta, strict=True)},
        'smearing': round(smearing, 5),
        'ols_cv': metrics(np.exp(y.to_numpy()), np.exp(ols_pred) * smearing),
        'gb_cv': metrics(np.exp(y.to_numpy()), np.exp(gb_pred) * smearing),
    }
    return result, fitted


def save(conn: psycopg.Connection, frame: pd.DataFrame, metrics_rows: list[dict], coefficient_rows: list[dict]):
    conn.execute('delete from valuation')
    conn.execute('delete from model_term')
    conn.execute('delete from model_metric')
    valued = frame[frame['model_price'].notna()]
    with conn.cursor() as cursor:
        cursor.executemany(
            'insert into valuation (listing_id, purpose, model_price, gap_pct, outlier, duplicate) '
            'values (%s, %s, %s, %s, %s, %s)',
            [
                (
                    int(r.listing_id),
                    r.purpose,
                    float(r.model_price),
                    float(r.model_gap_pct),
                    bool(r.outlier),
                    bool(r.duplicate),
                )
                for r in valued.itertuples()
            ],
        )
        cursor.executemany(
            'insert into model_term (purpose, term, value) values (%s, %s, %s)',
            [(r['purpose'], r['term'], r['value']) for r in coefficient_rows],
        )
        cursor.executemany(
            'insert into model_metric (purpose, model, rows, mape_pct, within_15_pct, r2_log) '
            'values (%s, %s, %s, %s, %s, %s)',
            [
                (r['purpose'], r['model'], r['rows'], r['mape_pct'], r['within_15_pct'], r['r2_log'])
                for r in metrics_rows
            ],
        )
    conn.commit()


def analyze(conn: psycopg.Connection, out: Path) -> dict:
    frame = load(conn)
    frame['outlier'] = flag_outliers(frame)
    frame['duplicate'] = duplicates(frame)
    clean = frame[~frame['outlier'] & ~frame['duplicate']]
    models, fitted = [], pd.Series(np.nan, index=frame.index)
    for purpose in ('sale', 'rent'):
        result, values = model(frame, purpose)
        models.append(result)
        fitted.loc[values.index] = values
    frame['model_price'] = fitted.round(0)
    frame['model_gap_pct'] = ((frame['price'] / frame['model_price'] - 1) * 100).round(1)
    frame['id'] = frame['source'] + ':' + frame['code'] + ':' + frame['purpose']
    out.mkdir(parents=True, exist_ok=True)
    columns = [
        'id',
        'source',
        'code',
        'url',
        'purpose',
        'category',
        'type',
        'price',
        'area',
        'price_m2',
        'bedrooms',
        'suites',
        'bathrooms',
        'parking',
        'address',
        'lat',
        'lon',
        'precision',
        'distance_km',
        'outlier',
        'duplicate',
        'model_price',
        'model_gap_pct',
    ]
    frame[columns].round({'price_m2': 2, 'distance_km': 3, 'lat': 6, 'lon': 6}).to_csv(
        out / 'listings.csv', index=False
    )
    metrics_rows = [
        {'purpose': m['purpose'], 'model': name, 'rows': m['rows'], **m[f'{key}_cv']}
        for m in models
        for name, key in (('hedonic regression', 'ols'), ('gradient boosting', 'gb'))
    ]
    coefficient_rows = [
        {'purpose': m['purpose'], 'term': term, 'value': value}
        for m in models
        for term, value in [*m['coefficients'].items(), (f'cat_{m["baseline"]}', 0.0), ('smearing', m['smearing'])]
    ]
    datasets = {
        'segments': summary(clean),
        'agencies': by_source(frame),
        'yields': yields(clean),
        'model_metrics': metrics_rows,
        'coefficients': coefficient_rows,
    }
    for name, rows in datasets.items():
        (out / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False))
    save(conn, frame, metrics_rows, coefficient_rows)
    return {
        'listings': len(frame),
        'outliers': int(frame['outlier'].sum()),
        'duplicates': int(frame['duplicate'].sum()),
        'models': models,
        **datasets,
    }
