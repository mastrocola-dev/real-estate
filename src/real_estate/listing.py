import re
from dataclasses import dataclass, field

PURPOSES = {
    'sell': 'sale',
    'venda': 'sale',
    'leaseout': 'rent',
    'aluguel': 'rent',
    'locação': 'rent',
}


@dataclass(frozen=True)
class Offer:
    purpose: str
    price: float
    available: bool = True


@dataclass
class Listing:
    external_id: str
    url: str
    type: str | None = None
    neighborhood: str | None = None
    address: str | None = None
    area_useful: float | None = None
    bedrooms: int | None = None
    suites: int | None = None
    bathrooms: int | None = None
    parking: int | None = None
    offers: list[Offer] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return any(o.available for o in self.offers)


def purpose(label: str) -> str | None:
    return PURPOSES.get(label.strip().lower())


def money(text: str) -> float | None:
    match = re.search(r'R\$\s*([\d.]+(?:,\d{2})?)', text)
    if not match:
        return None
    return float(match.group(1).replace('.', '').replace(',', '.'))


def area(text: str) -> float | None:
    match = re.search(r'([\d.,]+)\s*m²', text)
    if not match:
        return None
    value = match.group(1)
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', value):
        value = value.replace('.', '')
    return float(value.replace(',', '.'))


def count(text: str, *words: str) -> int | None:
    pattern = r'(\d+)\s+(?:' + '|'.join(words) + r')\b'
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else None
