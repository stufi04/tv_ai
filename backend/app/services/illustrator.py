"""Illustrates episodes with a text-to-image model on Cloudflare Workers AI."""

import base64
import binascii
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

CLOUDFLARE_API_URL = "https://api.cloudflare.com/client/v4"

IMAGE_STYLE = (
    "A cinematic, painterly illustration of a TV episode's key scene. "
    "No text, captions, logos or watermarks. Do not depict the likeness of real actors."
)

# flux-1-schnell accepts prompts of up to 2048 characters.
MAX_PROMPT_CHARS = 2048


class Illustrator(Protocol):
    async def illustrate(self, scene: str) -> str | None:
        """Return an image as a data: URL, or None if no image could be made."""
        ...


def sniff_image_type(data: bytes) -> str | None:
    """The docs disagree on whether flux returns JPEG or PNG, so look at the bytes."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def build_image_prompt(scene: str) -> str:
    return f"{IMAGE_STYLE}\n\nScene: {scene.strip()}"[:MAX_PROMPT_CHARS]


class CloudflareIllustrator:
    """Best effort: any failure is logged and returns None, because the story is still worth showing."""

    def __init__(self, http: httpx.AsyncClient, model: str, steps: int = 4) -> None:
        self._http = http
        self._model = model
        self._steps = steps

    async def illustrate(self, scene: str) -> str | None:
        try:
            response = await self._http.post(
                f"ai/run/{self._model}", json={"prompt": build_image_prompt(scene), "steps": self._steps}
            )
        except httpx.HTTPError as exc:
            logger.warning("Cloudflare image request failed: %s", exc.__class__.__name__)
            return None
        if response.is_error:
            logger.warning(
                "Cloudflare image model %s returned HTTP %d: %s", self._model, response.status_code, _errors(response)
            )
            return None

        try:
            encoded = response.json()["result"]["image"]
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, TypeError, binascii.Error):
            logger.warning("Cloudflare image model %s returned a response we could not read", self._model)
            return None

        mime_type = sniff_image_type(data)
        if mime_type is None:
            logger.warning("Cloudflare image model %s returned data that is not an image", self._model)
            return None
        return f"data:{mime_type};base64,{encoded}"


def _errors(response: httpx.Response) -> str:
    try:
        return "; ".join(error["message"] for error in response.json()["errors"]) or "no details"
    except (ValueError, KeyError, TypeError):
        return "no details"


def create_cloudflare_client(account_id: str, api_token: str, timeout: float = 30) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{CLOUDFLARE_API_URL}/accounts/{account_id}/",
        timeout=timeout,
        headers={"Authorization": f"Bearer {api_token}"},
    )
