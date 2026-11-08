from real_estate.robots import allowed, sitemaps

AGENT = 'real-estate-research/0.1'
KENLO = """User-agent: Claude-User
Allow: /
Disallow: /api/*
Disallow: /*+*

User-agent: *
Allow: /ads.txt
Disallow: /

Sitemap: https://x/sitemap.xml
"""


def test_wildcard_group_blocks_everything_but_ads():
    assert not allowed(KENLO, AGENT, 'https://x/imoveis/a-venda')
    assert allowed(KENLO, AGENT, 'https://x/ads.txt')


def test_named_group_with_wildcards_and_longest_match():
    assert allowed(KENLO, 'Claude-User', 'https://x/imoveis/a-venda/londrina/centro?pagina=2')
    assert not allowed(KENLO, 'Claude-User', 'https://x/api/listings')
    assert not allowed(KENLO, 'Claude-User', 'https://x/imoveis/a-venda/casa+sala/londrina')


def test_end_anchor_and_empty_rules():
    text = 'User-agent: *\nDisallow: /*.pdf$\nDisallow:\n'
    assert not allowed(text, AGENT, 'https://x/a/b.pdf')
    assert allowed(text, AGENT, 'https://x/a/b.pdf?download=1')
    assert allowed('', AGENT, 'https://x/anything')


def test_sitemaps():
    assert sitemaps(KENLO) == ['https://x/sitemap.xml']
