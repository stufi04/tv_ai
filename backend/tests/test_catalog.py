import pytest

from app.catalog import POPULAR_WEIGHT, ShowCatalog, UnknownShowError
from app.models import Show


def make_show(show_id: str, title: str, popularity: int, genres: list[str] | None = None, network: str = "") -> Show:
    return Show(
        id=show_id,
        title=title,
        year=2000,
        network=network or None,
        genres=genres or ["Drama"],
        summary="A show.",
        popularity=popularity,
    )


@pytest.fixture
def catalog() -> ShowCatalog:
    return ShowCatalog(
        [
            make_show("1", "The Office", 100, ["Comedy"], network="NBC"),
            make_show("2", "The Office", 80, ["Comedy"], network="BBC Two"),
            make_show("3", "Office Space Stories", 70, ["Comedy"]),
            make_show("4", "Back Office", 99, ["Drama"]),
            make_show("5", "Pokémon", 99, ["Animation"]),
            make_show("6", "Postofficer", 60, ["Drama"]),
            make_show("7", "Lost", 100, ["Drama"], network="ABC"),
            make_show("8", "Obscure Thing", 5, ["Drama"]),
        ]
    )


def ids(page_items: list[Show]) -> list[str]:
    return [show.id for show in page_items]


def test_search_ranks_exact_then_prefix_then_word_then_substring(catalog: ShowCatalog) -> None:
    page = catalog.search(query="office")

    # Exact titles first (more popular first), then prefix, then word match, then plain substring.
    assert ids(page.items) == ["1", "2", "3", "4", "6"]


def test_search_matches_network_after_titles(catalog: ShowCatalog) -> None:
    assert ids(catalog.search(query="abc").items) == ["7"]


def test_search_ignores_case_and_accents(catalog: ShowCatalog) -> None:
    assert ids(catalog.search(query="  POKEMON ").items) == ["5"]


def test_genre_filters_search_and_discover(catalog: ShowCatalog) -> None:
    assert ids(catalog.search(query="office", genre="Comedy").items) == ["1", "2", "3"]
    assert set(ids(catalog.search(genre="Comedy").items)) == {"1", "2", "3"}


def test_discover_puts_shuffled_popular_shows_first(catalog: ShowCatalog) -> None:
    popular = {"1", "4", "5", "7"}
    orders = {tuple(ids(catalog.search(seed=seed).items)) for seed in range(20)}

    for order in orders:
        assert set(order[:4]) == popular
        assert list(order[4:]) == ["2", "3", "6", "8"]  # the rest by popularity
    assert len(orders) > 1, "different seeds should shuffle the popular shows differently"


def test_discover_is_stable_for_a_seed(catalog: ShowCatalog) -> None:
    assert catalog.search(seed=42) == catalog.search(seed=42)


def test_paginates(catalog: ShowCatalog) -> None:
    first = catalog.search(seed=1, limit=3)
    second = catalog.search(seed=1, offset=3, limit=3)
    last = catalog.search(seed=1, offset=6, limit=3)

    assert (first.total, first.next_offset, second.next_offset, last.next_offset) == (8, 3, 6, None)
    assert len(ids(first.items + second.items + last.items)) == 8
    assert set(ids(first.items + second.items + last.items)) == {str(n) for n in range(1, 9)}


def test_no_matches(catalog: ShowCatalog) -> None:
    page = catalog.search(query="zzz")
    assert (page.items, page.total, page.next_offset) == ([], 0, None)


def test_genres_are_sorted_and_unique(catalog: ShowCatalog) -> None:
    assert catalog.genres() == ["Animation", "Comedy", "Drama"]


def test_get_many_reports_unknown_ids(catalog: ShowCatalog) -> None:
    assert ids(catalog.get_many(["7", "1"])) == ["7", "1"]
    with pytest.raises(UnknownShowError, match="nope"):
        catalog.get_many(["1", "nope"])


def test_popular_threshold_is_inclusive() -> None:
    catalog = ShowCatalog([make_show("a", "A", POPULAR_WEIGHT), make_show("b", "B", POPULAR_WEIGHT + 5)])
    assert set(ids(catalog.search(seed=3).items)) == {"a", "b"}
