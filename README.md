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
| `estate collect [source…]` | Collects every `capture = 'http'` source for the scope in `sources.toml`: raw pages, listings and one snapshot time per run; skips any URL `robots.txt` disallows |
| `estate import [dir]` | Imports the pages listed in `dir/manifest.jsonl` (default `samples/inbox`), one observation time per source, then moves the folder to `samples/imported/<run>` |

## Sources collected by this program

| Source | Platform | How |
|---|---|---|
| Perez | Keyspot | Search `/venda|alugar/pr/londrina/<bairro>?pagina=N`, 30 cards per page, total from the JSON-LD ItemList |
| Santamérica | Kurole | Category URLs for the neighborhood from `/xml/sitemap/sitemap.xml`, then `?pag=N`, 27 cards per page; cards often lack area |
| Veneza | Casasoft | Two sitemap requests (`transaction=v|l`); the listing URL carries type, bedrooms, neighborhood, parking, area, purpose and price |

## Sources captured by Claude (`capture = 'claude'`)

Inglaterra and Mônaco run on Kenlo, whose `robots.txt` blocks generic crawlers and allows `Claude-User`. They are never collected by this program. Only when the author asks, never scheduled:

1. Claude checks the `Claude-User` group of each site's `robots.txt`
2. Opens the sale and rent search pages of the scope in the Claude desktop app's browser (`?pagina=N`, 12 cards per page, 2 s apart) and runs `capture/kenlo.js` on each, in batches of 4 to 8 pages so each result is saved to a file on Claude's side
3. Runs `capture/extract.py` on those files, which writes the pages and `manifest.jsonl`, and delivers them to `samples/inbox/`
4. The author runs `estate import`

Captured pages keep the title, the JSON-LD and the listing cards without images. Launches (`/empreendimento/`) have no price and are skipped.

## Rules

- `robots.txt` that disallows everything stops collection for that source
- One request every 2 s per host, retries with backoff on 429 and 5xx
- Raw pages are kept before parsing; snapshots are appended, never overwritten
- Asking price is not transaction price

## Scope

`sources.toml`: city, neighborhoods (Centro first) and one entry per agency. Adapters are written per platform after `detect`.
