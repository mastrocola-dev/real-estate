alter table listing add column geom geometry(Point, 4326);
alter table listing add column geo_precision geo_precision;
alter table listing add column geo_source text;

create index listing_geom on listing using gist (geom);
