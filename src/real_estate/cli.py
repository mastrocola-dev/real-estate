import argparse
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from real_estate import config, db, detect
from real_estate.http import Client

SAMPLES = Path('samples')


def run_migrate(_args):
    with db.connect() as conn:
        applied = db.migrate(conn, config.load())
    print('applied: ' + (', '.join(applied) or 'nothing new'))


def run_detect(args):
    cfg = config.load()
    client = Client()
    ids = args.sources or list(cfg.sources)
    for source_id in ids:
        source = cfg.sources[source_id]
        robots = client.get(urljoin(source.base_url, '/robots.txt'))
        robots_txt = robots.text if robots.status_code == 200 else ''
        if detect.robots(robots_txt)[0]:
            print(f'{source_id}: robots.txt disallows everything, skipped')
            continue
        urls = [u for u in (source.base_url, source.search_url) if u]
        prints = []
        for url in urls:
            response = client.get(url)
            prints.append(
                detect.fingerprint(
                    str(response.url), response.status_code, response.text, robots_txt
                )
            )
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
        page_id = db.save_page(
            conn, args.source, str(response.url), response.status_code, response.text
        )
    path = SAMPLES / args.source / f'{slug(args.url)}.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text)
    print(f'{response.status_code} raw_page {page_id} {path}')


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
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
