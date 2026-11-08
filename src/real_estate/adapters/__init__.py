from real_estate.adapters import casasoft, kenlo, keyspot, kurole

PARSERS = {'kenlo': kenlo.parse_search}
COLLECTORS = {'keyspot': keyspot.collect, 'kurole': kurole.collect, 'casasoft': casasoft.collect}
