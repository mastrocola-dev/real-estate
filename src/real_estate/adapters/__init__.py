from real_estate.adapters import arbo, casasoft, kenlo, keyspot, kurole

COLLECTORS = {'keyspot': keyspot.collect, 'kurole': kurole.collect, 'casasoft': casasoft.collect, 'arbo': arbo.collect}


def parser(platform: str, city: str, neighborhoods: list[str]):
    areas = neighborhoods or [None]
    if platform == 'casasoft':
        return lambda html, url: (None, [i for n in areas for i in casasoft.parse_sitemap(html, city, n)])
    if platform == 'arbo':
        return lambda text, url: arbo.parse_detail(text, url, city)
    return {'kenlo': kenlo.parse_search, 'keyspot': keyspot.parse_search, 'kurole': kurole.parse_search}[platform]
