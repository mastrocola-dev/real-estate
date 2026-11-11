import base64
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

out = Path(sys.argv[1])
for result in sys.argv[2:]:
    text = ''.join(part['text'] for part in json.loads(Path(result).read_text()))
    batch, _ = json.JSONDecoder().raw_decode(text, text.find('{'))
    source = batch['source']
    pages = json.loads(gzip.decompress(base64.b64decode(batch['gz']))) if 'gz' in batch else batch['pages']
    for page in pages:
        parsed = urlparse(page['url'])
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', parsed.path + '-' + parsed.query).strip('-')
        target = out / source / f'{slug}.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page['html'])
        entry = {
            'source': source,
            'url': page['url'],
            'captured_at': page['captured_at'],
            'file': f'{source}/{target.name}',
        }
        with (out / 'manifest.jsonl').open('a') as manifest:
            manifest.write(json.dumps(entry) + '\n')
        print(target, len(page['html']))
