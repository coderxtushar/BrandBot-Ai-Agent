"""Pydantic models shared by the agent graph and the API.

Every LLM call returns one of these models (structured output), so nothing downstream
has to parse free text.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PlatformId(StrEnum):
    LINKEDIN = "linkedin"
    X = "x"
    THREADS = "threads"
    INSTAGRAM = "instagram"
    MEDIUM = "medium"
    YOUTUBE_SHORTS = "youtube_shorts"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

class BrandInput(BaseModel):
    """What the user tells us about themselves."""

    target_audience: str = Field(min_length=3, max_length=1000)
    expertise: str = Field(min_length=3, max_length=1000)
    tone_of_voice: str = Field(min_length=3, max_length=1000)
    content_pillars: str = Field(min_length=3, max_length=2000)
    past_posts: str = Field(
        default="",
        max_length=20000,
        description="Optional: paste a few of your own past posts so the AI can learn your voice.",
    )


class RunRequest(BaseModel):
    brand: BrandInput
    platforms: list[PlatformId] = Field(min_length=1)
    topic: str = Field(
        default="",
        max_length=500,
        description="Optional focus for this run. Empty = the planner picks from your pillars.",
    )
    variants: int = Field(default=1, ge=1, le=3, description="Drafts per platform (capped per platform).")
    brand_profile: "BrandProfile | None" = Field(
        default=None, description="Re-use a previously generated profile to skip that step."
    )


# ---------------------------------------------------------------------------
# Strategy & research
# ---------------------------------------------------------------------------

class VoiceGuide(BaseModel):
    traits: list[str] = Field(description="3-5 adjectives describing the voice")
    do: list[str] = Field(description="Concrete writing habits to follow")
    dont: list[str] = Field(description="Things this brand never does")


class BrandProfile(BaseModel):
    positioning: str = Field(description="One or two sentences: who you help and how you are different")
    audience_persona: str = Field(description="A short persona: role, goals, pains, what they scroll for")
    voice: VoiceGuide
    pillars: list[str] = Field(description="3-5 content pillars, each a short phrase")
    hashtags: list[str] = Field(description="10-15 relevant hashtags without the # sign")


class SearchQuery(BaseModel):
    query: str = Field(description="A specific web search query")
    topic: Literal["general", "news"] = Field(default="general", description="'news' for timely events")
    time_range: Literal["week", "month", "year"] | None = Field(
        default=None, description="Restrict to recent results when freshness matters"
    )


class ContentPlan(BaseModel):
    angle: str = Field(description="The single core idea/insight this run's content will express")
    pillar: str = Field(description="Which brand pillar this belongs to")
    queries: list[SearchQuery] = Field(min_length=1, max_length=3)


class Source(BaseModel):
    title: str
    url: str
    snippet: str


# ---------------------------------------------------------------------------
# Platform-specific content (one model per platform)
# ---------------------------------------------------------------------------

class LinkedInPost(BaseModel):
    hook: str = Field(description="First 1-2 lines, shown before '...see more'")
    body: str = Field(description="The rest of the post, short paragraphs separated by blank lines")
    closing_question: str = Field(description="An open question to invite comments")
    hashtags: list[str] = Field(description="3-5 hashtags without #")


class XThread(BaseModel):
    tweets: list[str] = Field(description="Each tweet <= 280 characters. First tweet is the hook.")
    hashtags: list[str] = Field(default_factory=list, description="0-2 hashtags without #")


class ThreadsPost(BaseModel):
    posts: list[str] = Field(description="1-5 posts, each <= 500 characters; first one is the hook")
    topic_tag: str = Field(default="", description="One Threads topic tag without #, optional")


class CarouselSlide(BaseModel):
    headline: str = Field(description="Big text on the slide, <= 8 words")
    text: str = Field(description="Supporting text, <= 25 words")


class InstagramPost(BaseModel):
    caption: str = Field(description="Caption; the first line is the hook")
    hashtags: list[str] = Field(description="5-15 hashtags without #")
    slides: list[CarouselSlide] = Field(description="3-8 carousel slides; slide 1 is a scroll-stopper")
    image_prompt: str = Field(description="A detailed prompt to generate the cover image")
    alt_text: str = Field(description="Accessible description of the cover image")


class MediumArticle(BaseModel):
    title: str
    subtitle: str
    body_markdown: str = Field(description="800-1500 word article in Markdown with ## sections")
    tags: list[str] = Field(description="Up to 5 Medium tags")


class ShortsBeat(BaseModel):
    seconds: str = Field(description="Time range, e.g. '0-3'")
    voiceover: str
    on_screen_text: str
    visual: str = Field(description="What the viewer sees (B-roll, face cam, screen recording...)")


class YouTubeShortScript(BaseModel):
    title: str = Field(description="<= 100 characters")
    hook: str = Field(description="What is said in the first 2 seconds")
    beats: list[ShortsBeat] = Field(description="Beats covering 30-60 seconds total")
    cta: str
    description: str
    hashtags: list[str] = Field(description="3-5 hashtags without #")


PlatformContent = (
    LinkedInPost | XThread | ThreadsPost | InstagramPost | MediumArticle | YouTubeShortScript
)


# ---------------------------------------------------------------------------
# Review & results
# ---------------------------------------------------------------------------

class Review(BaseModel):
    approved: bool = Field(description="True only if the content is ready to publish as-is")
    score: int = Field(ge=1, le=10, description="Overall quality 1-10")
    issues: list[str] = Field(
        default_factory=list,
        description="Specific, actionable problems. Empty if approved.",
    )


class PlatformResult(BaseModel):
    platform: PlatformId
    items: list[dict] = Field(default_factory=list, description="Platform content models, serialised")
    text: list[str] = Field(default_factory=list, description="Copy-ready plain text for each item")
    review: Review | None = None
    attempts: int = 0
    error: str | None = None


class RunResult(BaseModel):
    brand_profile: BrandProfile
    plan: ContentPlan
    sources: list[Source]
    results: list[PlatformResult]


RunRequest.model_rebuild()
