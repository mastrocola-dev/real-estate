import re
from urllib.parse import urlparse


def groups(text: str) -> list[tuple[list[str], list[tuple[bool, str]]]]:
    found, agents, rules, last = [], [], [], None
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        key, sep, value = line.partition(':')
        if not sep:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == 'user-agent':
            if last == 'rule':
                found.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
            last = 'agent'
        elif key in ('allow', 'disallow'):
            rules.append((key == 'allow', value))
            last = 'rule'
    if agents:
        found.append((agents, rules))
    return found


def matches(rule: str, path: str) -> bool:
    body = re.escape(rule.rstrip('$')).replace(r'\*', '.*')
    return re.match(body + ('$' if rule.endswith('$') else ''), path) is not None


def allowed(text: str, agent: str, url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or '/') + (f'?{parsed.query}' if parsed.query else '')
    found = groups(text)
    named = [rules for agents, rules in found if any(a != '*' and a in agent.lower() for a in agents)]
    rules = named[0] if named else next((rules for agents, rules in found if '*' in agents), [])
    best_length, verdict = -1, True
    for allow, rule in rules:
        if rule and matches(rule, path) and (len(rule) > best_length or (len(rule) == best_length and allow)):
            best_length, verdict = len(rule), allow
    return verdict


def sitemaps(text: str) -> list[str]:
    return [line.split(':', 1)[1].strip() for line in text.splitlines() if line.lower().startswith('sitemap:')]
