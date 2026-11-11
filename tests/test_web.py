import math

from real_estate.config import Config
from real_estate.web.query import Filters, estimate, inside, matches

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
ROW = {
    'purpose': 'sale',
    'category': 'apartment',
    'source': 'perez',
    'neighborhood': 'Centro',
    'precision': 'exact',
    'price': 400000.0,
    'area': 80.0,
    'price_m2': 5000.0,
    'gap_pct': -12.0,
    'bedrooms': 3,
    'suites': 1,
    'parking': None,
    'favorite': False,
    'outlier': False,
    'duplicate': False,
    'address': 'Rua Sergipe',
    'code': 'AP1',
    'type': 'Apartamento',
    'lat': 0.5,
    'lon': 0.5,
}


def test_inside():
    assert inside(0.5, 0.5, SQUARE)
    assert not inside(1.5, 0.5, SQUARE)


def test_matches():
    assert matches(ROW, Filters(purpose='sale', categories=['apartment'], bedrooms=3, text='sergipe', polygon=SQUARE))
    assert matches(ROW, Filters(gap=(None, -10), price=(300000, 500000)))
    assert not matches(ROW, Filters(parking=1))
    assert not matches(ROW, Filters(favorites=True))
    assert not matches(ROW, Filters(price_m2=(6000, None)))


def test_canonical():
    cfg = Config('Londrina', 'PR', ['Centro', 'Alvorada'], {}, {'Alvorada': ['Jardim Alvorada']})
    assert cfg.canonical('JARDIM ALVORADA') == 'Alvorada'
    assert cfg.canonical('jardim-alvorada') == 'Alvorada'
    assert cfg.canonical('GLEBA PALHANO') == 'Gleba Palhano'
    assert cfg.canonical('jardim-dos-pioneiros') == 'Jardim dos Pioneiros'
    assert cfg.spellings == ['Centro', 'Alvorada', 'Jardim Alvorada']


def test_estimate():
    terms = {'intercept': 1.0, 'log_area': 1.0, 'cat_house': 0.5, 'bedrooms': 0.1, 'distance_km': 0.0, 'smearing': 1.0}
    assert math.isclose(estimate(terms, 'house', 100, {'bedrooms': 2}), math.exp(1 + math.log(100) + 0.5 + 0.2))


def test_coordinates():
    from real_estate.enrich import coordinates

    jsonld = '{"geo":{"@type":"GeoCoordinates","latitude":-23.31,"longitude":-51.16}}'
    attrs = '<div data-latitude="-23.32" data-longitude="-51.17"></div>'
    leaflet = "initLeafletMap('-23.33', '-51.15', 16)"
    assert coordinates(jsonld) == (-23.31, -51.16)
    assert coordinates(attrs) == (-23.32, -51.17)
    assert coordinates(leaflet) == (-23.33, -51.15)
    assert coordinates('"latitude": 0.0, "longitude": 0.0') is None
    assert coordinates("initLeafletMap('map_leaflet', -23.34, -51.14)") == (-23.34, -51.14)


def test_listing_point_wins_over_agency_jsonld():
    from real_estate.enrich import address, coordinates

    html = (
        '<script type="application/ld+json">{"@type":"RealEstateAgent","geo":{"@type":"GeoCoordinates",'
        '"latitude": -23.317227759345297, "longitude": -51.16135611534255}}</script>'
        '<p class="card__address">\n   R. Araçatuba, 276 -\n   \n   Amaro. Londrina/PR</p>'
        '<div id="map" data-latitude="-23.3020848" data-longitude="-51.189656"></div>'
    )
    assert coordinates(html) == (-23.3020848, -51.189656)
    assert address(html) == 'R. Araçatuba, 276'
