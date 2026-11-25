"""Image generation behind a tiny interface, so tests and demo mode can use a fake."""

import logging
from dataclasses import dataclass
from typing import Protocol

from backend.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime: str
    model: str


class ImageGenerator(Protocol):
    async def generate(self, prompt: str, aspect_ratio: str) -> GeneratedImage: ...


class GeminiImageGenerator:
    """Gemini native image generation ("Nano Banana" family)."""

    def __init__(self, settings: Settings):
        from google import genai

        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.gemini_image_model

    async def generate(self, prompt: str, aspect_ratio: str) -> GeneratedImage:
        from google.genai import types

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        for candidate in response.candidates or []:
            for part in (candidate.content.parts if candidate.content else None) or []:
                if part.inline_data and part.inline_data.data:
                    return GeneratedImage(part.inline_data.data, part.inline_data.mime_type or "image/png", self._model)
        reason = response.prompt_feedback.block_reason if response.prompt_feedback else None
        raise RuntimeError(f"The image model returned no image{f' (blocked: {reason})' if reason else ''}.")


class FakeImageGenerator:
    """Offline placeholder: an SVG gradient in the requested aspect ratio, labelled with the prompt."""

    PALETTES = [("#4f46e5", "#ec4899"), ("#0ea5e9", "#22c55e"), ("#f97316", "#eab308"), ("#8b5cf6", "#06b6d4")]

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.prompts: list[tuple[str, str]] = []
        self.fail = False

    async def generate(self, prompt: str, aspect_ratio: str) -> GeneratedImage:
        import asyncio
        from html import escape

        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("image model unavailable")
        self.prompts.append((prompt, aspect_ratio))
        w, h = (int(x) for x in aspect_ratio.split(":"))
        width, height = 1080, round(1080 * h / w)
        a, b = self.PALETTES[len(self.prompts) % len(self.PALETTES)]
        label = escape(prompt[:60] + ("…" if len(prompt) > 60 else ""))
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<radialGradient id="r" cx="0.75" cy="0.2" r="0.6"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>
<rect width="100%" height="100%" fill="url(#g)"/><rect width="100%" height="100%" fill="url(#r)"/>
<circle cx="{width * 0.2:.0f}" cy="{height * 0.8:.0f}" r="{width * 0.25:.0f}" fill="#fff" fill-opacity=".08"/>
<text x="54" y="{height - 64}" font-family="Helvetica, Arial, sans-serif" font-size="30" fill="#fff" fill-opacity=".85">{label}</text>
<text x="54" y="80" font-family="Helvetica, Arial, sans-serif" font-size="26" fill="#fff" fill-opacity=".7">DEMO IMAGE · {aspect_ratio}</text>
</svg>"""
        return GeneratedImage(svg.encode(), "image/svg+xml", "fake-image")
