from real_estate.detect import fingerprint

HTML = """
<html><head>
<meta name="generator" content="WordPress 6.5">
<script src="https://cdn.jetimob.com/app.js"></script>
<script src="/static/local.js"></script>
<link href="https://www.example.com.br/style.css" rel="stylesheet">
<script type="application/ld+json">{"offers": {"price": 420000}}</script>
</head><body><p>R$ 1.650.000</p><p>R$ 890.000</p></body></html>
"""


def test_fingerprint_reads_platform_hosts_and_prices():
    result = fingerprint('https://www.example.com.br/', 200, HTML)
    assert result.platforms == ['jetimob']
    assert result.generator == 'WordPress 6.5'
    assert result.hosts == ['cdn.jetimob.com']
    assert result.prices_in_html == 2
    assert result.jsonld_offers == 1
