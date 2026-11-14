"""Browser tests covering the main user journeys."""

import re

import pytest
from playwright.sync_api import Locator, Page, expect

from app.services.episode_generator import RateLimitedError
from tests.fakes import FakeEpisodeGenerator

pytestmark = pytest.mark.e2e


def show_cards(page: Page) -> Locator:
    return page.get_by_role("list", name="Shows").get_by_role("button")


def show_card(page: Page, title: str) -> Locator:
    return show_cards(page).filter(has=page.get_by_text(title, exact=True))


def test_browse_search_and_filter_by_genre(page: Page) -> None:
    page.goto("/")
    expect(show_card(page, "Breaking Bad")).to_be_visible()

    page.get_by_label("Search shows").fill("office")
    expect(show_cards(page)).to_have_count(1)
    expect(show_card(page, "The Office")).to_be_visible()

    page.get_by_label("Search shows").fill("")
    page.get_by_label("Genre").select_option("Animation")
    expect(show_card(page, "Rick and Morty")).to_be_visible()
    expect(show_card(page, "Breaking Bad")).to_have_count(0)

    page.get_by_label("Search shows").fill("no such show")
    expect(page.get_by_text("No shows match your filters.")).to_be_visible()


def test_generate_new_episode_for_one_show(page: Page, e2e_generator: FakeEpisodeGenerator) -> None:
    page.goto("/")

    show_card(page, "Breaking Bad").click()
    page.get_by_role("button", name="Generate episode").click()

    episode = page.get_by_role("article", name="Generated episode")
    expect(episode.get_by_role("heading", name="Breaking Bad: The Lost Episode")).to_be_visible()
    expect(episode.get_by_text("By Friday, nothing would ever be the same.")).to_be_visible()
    expect(episode.get_by_role("img")).to_have_attribute("src", re.compile(r"^data:image/png;base64,"))
    assert e2e_generator.requests == [["breaking-bad"]]


def test_generate_crossover_and_limit_selection_to_two(page: Page, e2e_generator: FakeEpisodeGenerator) -> None:
    page.goto("/")

    show_card(page, "The Office").click()
    show_card(page, "Stranger Things").click()

    expect(show_card(page, "The Office")).to_have_attribute("aria-pressed", "true")
    expect(show_card(page, "Friends")).to_be_disabled()

    page.get_by_role("button", name="Generate crossover").click()

    heading = page.get_by_role("heading", name="The Office x Stranger Things: The Lost Episode")
    expect(heading).to_be_visible()
    assert e2e_generator.requests == [["the-office", "stranger-things"]]


def test_deselecting_and_clearing_shows(page: Page) -> None:
    page.goto("/")
    generate = page.get_by_role("button", name=re.compile(r"^Generate"))

    show_card(page, "Friends").click()
    show_card(page, "Friends").click()
    expect(generate).to_be_disabled()

    show_card(page, "Friends").click()
    page.get_by_role("button", name="Clear").click()
    expect(show_card(page, "Friends")).to_have_attribute("aria-pressed", "false")
    expect(generate).to_be_disabled()


def test_shows_error_when_generation_fails(page: Page, e2e_generator: FakeEpisodeGenerator) -> None:
    e2e_generator.error = RateLimitedError("Gemini rate limit reached. Please try again shortly.")
    page.goto("/")

    show_card(page, "Sherlock").click()
    page.get_by_role("button", name="Generate episode").click()

    expect(page.get_by_role("alert")).to_have_text("Gemini rate limit reached. Please try again shortly.")
    expect(page.get_by_role("article", name="Generated episode")).to_have_count(0)
