create extension if not exists postgis;

create type purpose as enum ('sale', 'rent');
create type geo_precision as enum ('exact', 'street', 'neighborhood');

create table source (
  id text primary key,
  name text not null,
  base_url text not null,
  platform text
);

create table raw_page (
  id bigserial primary key,
  source_id text not null references source,
  url text not null,
  fetched_at timestamptz not null default now(),
  status smallint not null,
  body text not null
);

create index raw_page_lookup on raw_page (source_id, url, fetched_at desc);

create table listing (
  id bigserial primary key,
  source_id text not null references source,
  external_id text not null,
  url text not null,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  active boolean not null default true,
  unique (source_id, external_id)
);

create table snapshot (
  listing_id bigint not null references listing,
  observed_at timestamptz not null default now(),
  purpose purpose not null,
  type text,
  price numeric(14, 2) not null check (price > 0),
  condo_fee numeric(12, 2),
  iptu numeric(12, 2),
  area_useful numeric(10, 2),
  area_total numeric(10, 2),
  bedrooms smallint,
  suites smallint,
  bathrooms smallint,
  parking smallint,
  address text,
  neighborhood text,
  geom geometry(Point, 4326),
  geo_precision geo_precision,
  raw_page_id bigint references raw_page,
  primary key (listing_id, observed_at, purpose)
);

create index snapshot_geom on snapshot using gist (geom);

create table region (
  id serial primary key,
  kind text not null,
  name text not null,
  geom geometry(MultiPolygon, 4326) not null,
  unique (kind, name)
);

create index region_geom on region using gist (geom);
