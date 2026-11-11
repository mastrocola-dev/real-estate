import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from real_estate.listing import slug

LOWER = {'de', 'da', 'do', 'das', 'dos', 'e', 'di'}


def tidy(name: str) -> str:
    words = name.replace('-', ' ').split() if ' ' not in name.strip() else name.split()
    return ' '.join(
        w.lower() if i and w.lower() in LOWER else w[:1].upper() + w[1:].lower() for i, w in enumerate(words)
    )


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    base_url: str
    search_url: str | None = None
    platform: str | None = None
    capture: str = 'http'


@dataclass(frozen=True)
class Config:
    city: str
    state: str
    neighborhoods: list[str]
    sources: dict[str, Source]
    aliases: dict[str, list[str]] = field(default_factory=dict)

    def names(self, neighborhood: str) -> list[str]:
        return [neighborhood, *self.aliases.get(neighborhood, [])]

    @property
    def spellings(self) -> list[str]:
        return [n for neighborhood in self.neighborhoods for n in self.names(neighborhood)]

    def canonical(self, name: str | None) -> str | None:
        if not name:
            return name
        key = slug(name)
        for neighborhood in [*self.neighborhoods, *self.aliases]:
            if key in {slug(n) for n in self.names(neighborhood)}:
                return neighborhood
        return tidy(name)


def load(path: Path = Path('sources.toml')) -> Config:
    data = tomllib.loads(path.read_text())
    sources = {key: Source(id=key, **value) for key, value in data['sources'].items()}
    return Config(sources=sources, aliases=data.get('aliases', {}), **data['scope'])
