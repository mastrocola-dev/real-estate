import tomllib
from dataclasses import dataclass
from pathlib import Path


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
    neighborhoods: list[str]
    sources: dict[str, Source]


def load(path: Path = Path('sources.toml')) -> Config:
    data = tomllib.loads(path.read_text())
    sources = {key: Source(id=key, **value) for key, value in data['sources'].items()}
    return Config(sources=sources, **data['scope'])
