create table favorite (
  listing_id bigint primary key references listing,
  note text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table valuation (
  listing_id bigint not null references listing,
  purpose purpose not null,
  model_price numeric(14, 2) not null,
  gap_pct numeric(8, 2) not null,
  outlier boolean not null,
  duplicate boolean not null,
  computed_at timestamptz not null default now(),
  primary key (listing_id, purpose)
);

create table model_term (
  purpose purpose not null,
  term text not null,
  value double precision not null,
  primary key (purpose, term)
);

create table model_metric (
  purpose purpose not null,
  model text not null,
  rows integer not null,
  mape_pct numeric(6, 2) not null,
  within_15_pct numeric(6, 2) not null,
  r2_log numeric(6, 3) not null,
  primary key (purpose, model)
);
