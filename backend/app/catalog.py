import random
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from pydantic import TypeAdapter

from app.models import Show, ShowPage

shows_adapter = TypeAdapter(list[Show])

# Shows at or above this TVmaze weight are shuffled to the top of the default "discover" listing.
# In the real data, 99-100 is ~700 well-known shows; 90+ would be ~5,000 and include many obscure ones.
POPULAR_WEIGHT = 99


class UnknownShowError(LookupError):
    def __init__(self, show_ids: Iterable[str]) -> None:
        self.show_ids = list(show_ids)
        super().__init__(f"Unknown show id(s): {', '.join(self.show_ids)}")


def normalize(text: str) -> str:
    """Casefold and strip accents, so "pokemon" matches "Pokémon"."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _strip_article(title: str) -> str:
    """ "the office" -> "office", so a search for "office" treats The Office as an exact match."""
    for article in ("the ", "a ", "an "):
        if title.startswith(article):
            return title[len(article) :]
    return title


def _match_rank(title: str, network: str, term: str) -> int | None:
    """Lower is better; None means no match."""
    bare_title = _strip_article(title)
    if term in (title, bare_title):
        return 0
    if title.startswith(term) or bare_title.startswith(term):
        return 1
    if f" {term}" in f" {title}":
        return 2
    if term in title:
        return 3
    if term in network:
        return 4
    return None


class ShowCatalog:
    """Read-only, in-memory collection of TV shows with search and pagination."""

    def __init__(self, shows: Iterable[Show]) -> None:
        self._shows = {show.id: show for show in shows}
        by_popularity = sorted(self._shows.values(), key=lambda show: (-show.popularity, show.title))
        self._by_popularity = by_popularity
        # (show, normalized title, normalized network) in popularity order, precomputed for fast search.
        self._search_index = [(show, normalize(show.title), normalize(show.network or "")) for show in by_popularity]
        self._genres = sorted({genre for show in by_popularity for genre in show.genres})

    @classmethod
    def from_json_file(cls, path: Path) -> "ShowCatalog":
        return cls(shows_adapter.validate_json(path.read_bytes()))

    def __len__(self) -> int:
        return len(self._shows)

    def all(self) -> list[Show]:
        return list(self._by_popularity)

    def genres(self) -> list[str]:
        return list(self._genres)

    def get_many(self, show_ids: Iterable[str]) -> list[Show]:
        show_ids = list(show_ids)
        missing = [show_id for show_id in show_ids if show_id not in self._shows]
        if missing:
            raise UnknownShowError(missing)
        return [self._shows[show_id] for show_id in show_ids]

    def search(self, *, query: str = "", genre: str = "", offset: int = 0, limit: int = 24, seed: int = 0) -> ShowPage:
        """Search title/network (best matches first), or, with no query, a seeded random mix of popular shows."""
        term = normalize(query.strip())

        if term:
            ranked: list[tuple[int, Show]] = []
            # The index is in popularity order and sort() is stable, so ties stay most-popular-first.
            for show, title, network in self._search_index:
                # Cheap substring check first: almost every show fails it, skipping the ranking work.
                if (term in title or term in network) and (not genre or genre in show.genres):
                    rank = _match_rank(title, network, term)
                    if rank is not None:
                        ranked.append((rank, show))
            ranked.sort(key=lambda pair: pair[0])
            results = [show for _, show in ranked]
        else:
            candidates = [show for show in self._by_popularity if not genre or genre in show.genres]
            popular = [show for show in candidates if show.popularity >= POPULAR_WEIGHT]
            random.Random(seed).shuffle(popular)
            results = popular + [show for show in candidates if show.popularity < POPULAR_WEIGHT]

        end = offset + limit
        return ShowPage(
            items=results[offset:end],
            total=len(results),
            next_offset=end if end < len(results) else None,
        )
