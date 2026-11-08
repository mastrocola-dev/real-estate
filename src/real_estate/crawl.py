from collections.abc import Callable, Iterator

from real_estate.http import Client
from real_estate.listing import Listing

Page = tuple[str, int, str, list[Listing]]
Parser = Callable[[str, str], tuple[int | None, list[Listing]]]


def paginate(
    client: Client, url: str, page_url: Callable[[str, int], str], parse: Parser, limit: int = 100
) -> Iterator[Page]:
    seen = 0
    for page in range(1, limit + 1):
        response = client.get(url if page == 1 else page_url(url, page))
        total, listings = parse(response.text, str(response.url)) if response.status_code == 200 else (None, [])
        yield str(response.url), response.status_code, response.text, listings
        seen += len(listings)
        if not listings or total is None or seen >= total:
            return
