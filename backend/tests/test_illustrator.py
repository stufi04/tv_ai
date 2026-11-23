"""Cloudflare Workers AI image generation, with the API replaced by httpx.MockTransport."""

import asyncio
import base64
import json
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.dependencies import build_illustrator
from app.services.illustrator import (
    IMAGE_STYLE,
    MAX_PROMPT_CHARS,
    CloudflareIllustrator,
    create_cloudflare_client,
    sniff_image_type,
)

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-body"
PNG = b"\x89PNG\r\n\x1a\n" + b"png-body"
MODEL = "@cf/black-forest-labs/flux-1-schnell"


def image_reply(data: bytes) -> httpx.Response:
    return httpx.Response(200, json={"result": {"image": base64.b64encode(data).decode()}, "success": True})


class FakeCloudflare:
    def __init__(self, reply: httpx.Response | Exception) -> None:
        self.reply = reply
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[0].content)


def illustrate(fake: FakeCloudflare, scene: str = "A diner at midnight.") -> str | None:
    http = create_cloudflare_client("acct-123", "cf-token")
    http._transport = httpx.MockTransport(fake.handler)  # noqa: SLF001 - keep the real base URL and headers
    return asyncio.run(CloudflareIllustrator(http, MODEL).illustrate(scene))


@pytest.mark.parametrize(("data", "mime"), [(JPEG, "image/jpeg"), (PNG, "image/png")])
def test_returns_data_url_with_detected_type(data: bytes, mime: str) -> None:
    result = illustrate(FakeCloudflare(image_reply(data)))

    assert result == f"data:{mime};base64,{base64.b64encode(data).decode()}"


def test_calls_the_model_endpoint_with_token_and_styled_prompt() -> None:
    fake = FakeCloudflare(image_reply(JPEG))

    illustrate(fake, scene="  A diner at midnight.  ")

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"https://api.cloudflare.com/client/v4/accounts/acct-123/ai/run/{MODEL}"
    assert request.headers["authorization"] == "Bearer cf-token"
    assert fake.body["prompt"] == f"{IMAGE_STYLE}\n\nScene: A diner at midnight."
    assert fake.body["steps"] == 4


def test_truncates_long_prompts() -> None:
    fake = FakeCloudflare(image_reply(JPEG))

    illustrate(fake, scene="x" * 5000)

    assert len(fake.body["prompt"]) == MAX_PROMPT_CHARS


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(httpx.Response(403, json={"errors": [{"message": "upgrade required"}]}), id="forbidden"),
        pytest.param(httpx.Response(429, json={"errors": []}), id="daily allowance used up"),
        pytest.param(httpx.Response(500, text="oops"), id="server error"),
        pytest.param(httpx.Response(200, json={"result": {}}), id="no image field"),
        pytest.param(httpx.Response(200, json={"result": {"image": "not base64!"}}), id="bad base64"),
        pytest.param(image_reply(b"just some text"), id="not an image"),
        pytest.param(httpx.Response(200, text="<html>"), id="not json"),
        pytest.param(httpx.ReadTimeout("slow"), id="timeout"),
        pytest.param(httpx.ConnectError("offline"), id="connection error"),
    ],
)
def test_failures_mean_no_image(reply: httpx.Response | Exception) -> None:
    assert illustrate(FakeCloudflare(reply)) is None


def test_sniff_image_type() -> None:
    assert sniff_image_type(JPEG) == "image/jpeg"
    assert sniff_image_type(PNG) == "image/png"
    assert sniff_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_image_type(b"GIF89a") is None


@pytest.mark.parametrize(
    ("overrides", "enabled"),
    [
        pytest.param({"cloudflare_account_id": "a", "cloudflare_api_token": "t"}, True, id="configured"),
        pytest.param({"cloudflare_account_id": "a"}, False, id="no token"),
        pytest.param({"cloudflare_api_token": "t"}, False, id="no account"),
        pytest.param(
            {"cloudflare_account_id": "a", "cloudflare_api_token": "t", "generate_images": False}, False, id="off"
        ),
    ],
)
def test_images_are_on_only_when_configured(overrides: dict[str, Any], enabled: bool) -> None:
    illustrator = build_illustrator(Settings(_env_file=None, **overrides))

    assert (illustrator is not None) is enabled
