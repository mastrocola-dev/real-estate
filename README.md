# real-estate

Private, local-only. Collects sale and rental listings from local real estate agencies in Londrina into PostgreSQL + PostGIS, to price properties by region and characteristics.

## Setup

```sh
sudo -u postgres createuser "$USER"
sudo -u postgres createdb -O "$USER" real_estate
sudo -u postgres psql -d real_estate -c 'create extension postgis'
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
estate migrate
```

`DATABASE_URL` defaults to `dbname=real_estate` over the local socket (peer authentication, no password).

## Commands

| Command | Does |
|---|---|
| `estate migrate` | Applies `db/*.sql` once each and syncs `sources.toml` into `source` |
| `estate detect [source…]` | Fingerprints each site: platform, external hosts, prices in HTML, JSON-LD offers, robots.txt, sitemaps. Needs no database |
| `estate fetch <source> <url>` | Stores the page in `raw_page` and in `samples/<source>/` |

## Rules

- `robots.txt` that disallows everything stops collection for that source
- One request every 2 s per host, retries with backoff on 429 and 5xx
- Raw pages are kept before parsing; snapshots are appended, never overwritten
- Asking price is not transaction price

## Scope

`sources.toml`: city, neighborhoods (Centro first) and one entry per agency. Adapters are written per platform after `detect`.
