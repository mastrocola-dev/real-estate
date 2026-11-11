from datetime import datetime

import psycopg

from real_estate.listing import Listing
from real_estate.locate import inside


def import_listings(
    conn: psycopg.Connection,
    source_id: str,
    raw_page_id: int,
    observed_at: datetime,
    listings: list[Listing],
) -> int:
    snapshots = 0
    for item in listings:
        (listing_id,) = conn.execute(
            'insert into listing (source_id, external_id, url, first_seen, last_seen, active) '
            'values (%s, %s, %s, %s, %s, %s) '
            'on conflict (source_id, external_id) do update set url = excluded.url, '
            'last_seen = greatest(listing.last_seen, excluded.last_seen), active = excluded.active '
            'returning id',
            [source_id, item.external_id, item.url, observed_at, observed_at, item.active],
        ).fetchone()
        if item.point and inside(*item.point):
            conn.execute(
                'update listing set geom = st_setsrid(st_makepoint(%s, %s), 4326), geo_precision = %s, '
                'geo_source = %s where id = %s',
                [item.point[1], item.point[0], 'exact', 'listing data', listing_id],
            )
        for offer in item.offers:
            if not offer.available:
                continue
            snapshots += conn.execute(
                'insert into snapshot (listing_id, observed_at, purpose, type, price, area_useful, area_total, '
                'bedrooms, suites, bathrooms, parking, address, neighborhood, condo_fee, iptu, raw_page_id) '
                'values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) '
                'on conflict do nothing',
                [
                    listing_id,
                    observed_at,
                    offer.purpose,
                    item.type,
                    offer.price,
                    item.area_useful,
                    item.area_total,
                    item.bedrooms,
                    item.suites,
                    item.bathrooms,
                    item.parking,
                    item.address,
                    item.neighborhood,
                    item.condo_fee,
                    item.iptu,
                    raw_page_id,
                ],
            ).rowcount
    conn.commit()
    return snapshots
