import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

out = Path(sys.argv[1])
source = sys.argv[2]
for result in sys.argv[3:]:
    for part in json.loads(Path(result).read_text()):
        text = part['text']
        start = text.find('{')
        if start == -1:
            continue
        try:
            page, _ = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if not isinstance(page, dict) or 'html' not in page:
            continue
        parsed = urlparse(page['url'])
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', parsed.path + '-' + parsed.query).strip('-')
        target = out / source / f'{slug}.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page['html'])
        with (out / 'manifest.jsonl').open('a') as manifest:
            manifest.write(
                json.dumps(
                    {
                        'source': source,
                        'url': page['url'],
                        'captured_at': page['captured_at'],
                        'file': f'{source}/{target.name}',
                    }
                )
                + '\n'
            )
        print(target, len(page['html']))
