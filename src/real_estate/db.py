import os
from pathlib import Path

import psycopg

from real_estate.config import Config

MIGRATIONS = Path('db')


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ.get('DATABASE_URL', 'dbname=real_estate'))


def migrate(conn: psycopg.Connection, config: Config) -> list[str]:
    conn.execute(
        'create table if not exists schema_migration '
        '(name text primary key, applied_at timestamptz not null default now())'
    )
    done = {row[0] for row in conn.execute('select name from schema_migration')}
    applied = []
    for path in sorted(MIGRATIONS.glob('*.sql')):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute('insert into schema_migration (name) values (%s)', [path.name])
        applied.append(path.name)
    sync_sources(conn, config)
    conn.commit()
    return applied


def sync_sources(conn: psycopg.Connection, config: Config):
    for s in config.sources.values():
        conn.execute(
            'insert into source (id, name, base_url, platform) values (%s, %s, %s, %s) '
            'on conflict (id) do update set name = excluded.name, base_url = excluded.base_url, '
            'platform = excluded.platform',
            [s.id, s.name, s.base_url, s.platform],
        )


def save_page(conn: psycopg.Connection, source_id: str, url: str, status: int, body: str) -> int:
    row = conn.execute(
        'insert into raw_page (source_id, url, status, body) values (%s, %s, %s, %s) returning id',
        [source_id, url, status, body],
    ).fetchone()
    conn.commit()
    return row[0]
