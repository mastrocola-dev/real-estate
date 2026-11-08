import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from real_estate import config, db, detect, robots, store
from real_estate.adapters import COLLECTORS, PARSERS
from real_estate.http import USER_AGENT, Client, Disallowed

SAMPLES = Path('samples')


def run_migrate(_args):
    with db.connect() as conn:
        applied = db.migrate(conn, config.load())
    print('applied: ' + (', '.join(applied) or 'nothing new'))


def run_detect(args):
    cfg = config.load()
    client = Client()
    for source_id in args.sources or list(cfg.sources):
        source = cfg.sources[source_id]
        robots_txt = client.robots(source.base_url)
        if not robots.allowed(robots_txt, USER_AGENT, source.base_url):
            print(f'{source_id}: robots.txt disallows this program, skipped')
            continue
        prints = []
        for url in (u for u in (source.base_url, source.search_url) if u):
            response = client.get(url)
            prints.append(detect.fingerprint(str(response.url), response.status_code, response.text, robots_txt))
        print(detect.report(source_id, prints))


def slug(url: str) -> str:
    parsed = urlparse(url)
    return re.sub(r'[^a-zA-Z0-9]+', '-', parsed.path + parsed.query).strip('-') or 'index'


def run_fetch(args):
    cfg = config.load()
    if args.source not in cfg.sources:
        raise SystemExit(f'unknown source: {args.source}')
    response = Client().get(args.url)
    with db.connect() as conn:
        page_id = db.save_page(conn, args.source, str(response.url), response.status_code, response.text)
    path = SAMPLES / args.source / f'{slug(args.url)}.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text)
    print(f'{response.status_code} raw_page {page_id} {path}')


def run_import(args):
    inbox = Path(args.dir)
    entries = [json.loads(line) for line in (inbox / 'manifest.jsonl').read_text().splitlines()]
    cfg = config.load()
    runs = {e['source']: min(x['captured_at'] for x in entries if x['source'] == e['source']) for e in entries}
    with db.connect() as conn:
        for e in entries:
            source = cfg.sources[e['source']]
            html = (inbox / e['file']).read_text()
            total, listings = PARSERS[source.platform](html, e['url'])
            page_id = db.save_page(conn, source.id, e['url'], 200, html)
            observed_at = datetime.fromisoformat(runs[source.id])
            snapshots = store.import_listings(conn, source.id, page_id, observed_at, listings)
            print(f'{source.id} {e["url"]} cards={len(listings)} snapshots={snapshots}')
    target = Path('samples/imported') / min(runs.values()).replace(':', '-')
    target.parent.mkdir(parents=True, exist_ok=True)
    inbox.rename(target)
    print(f'moved to {target}')


def run_collect(args):
    cfg = config.load()
    client = Client()
    observed_at = datetime.now(UTC)
    ids = args.sources or [s.id for s in cfg.sources.values() if s.capture == 'http' and s.platform in COLLECTORS]
    with db.connect() as conn:
        for source_id in ids:
            source = cfg.sources[source_id]
            if source.capture != 'http' or source.platform not in COLLECTORS:
                print(f'{source_id}: not collected by this program')
                continue
            for neighborhood in cfg.neighborhoods:
                pages = COLLECTORS[source.platform](client, source.base_url, cfg.city, cfg.state, neighborhood)
                try:
                    for url, status, body, listings in pages:
                        page_id = db.save_page(conn, source.id, url, status, body)
                        snapshots = store.import_listings(conn, source.id, page_id, observed_at, listings)
                        print(f'{source.id} {status} {url} cards={len(listings)} snapshots={snapshots}')
                except Disallowed as blocked:
                    print(f'{source.id}: robots.txt disallows {blocked}')


def main():
    parser = argparse.ArgumentParser(prog='estate')
    commands = parser.add_subparsers(required=True)
    commands.add_parser('migrate').set_defaults(run=run_migrate)
    detect_cmd = commands.add_parser('detect')
    detect_cmd.add_argument('sources', nargs='*')
    detect_cmd.set_defaults(run=run_detect)
    fetch_cmd = commands.add_parser('fetch')
    fetch_cmd.add_argument('source')
    fetch_cmd.add_argument('url')
    fetch_cmd.set_defaults(run=run_fetch)
    collect_cmd = commands.add_parser('collect')
    collect_cmd.add_argument('sources', nargs='*')
    collect_cmd.set_defaults(run=run_collect)
    import_cmd = commands.add_parser('import')
    import_cmd.add_argument('dir', nargs='?', default='samples/inbox')
    import_cmd.set_defaults(run=run_import)
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
