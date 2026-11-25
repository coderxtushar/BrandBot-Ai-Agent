"""Pydantic models shared by the agent graph and the API.

Every LLM call returns one of these models (structured output), so nothing downstream
has to parse free text.
"""

from datetime import datetime
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
    visual_style: str = Field(
        default="",
        description="Visual identity for images: palette, mood, imagery style (e.g. 'warm editorial photos, navy and amber')",
    )


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



# ---------------------------------------------------------------------------
# Persistence API (brands & run history)
# ---------------------------------------------------------------------------

RunStatus = Literal["running", "awaiting_plan", "completed", "failed", "cancelled"]
DraftStatus = Literal["draft", "approved", "rejected"]


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    input: BrandInput


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    input: BrandInput | None = Field(default=None, description="Changing the input clears the saved profile")


class BrandOut(BaseModel):
    id: str
    name: str
    input: BrandInput
    profile: BrandProfile | None
    profile_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BrandRunRequest(BaseModel):
    platforms: list[PlatformId] = Field(min_length=1)
    topic: str = Field(default="", max_length=500)
    variants: int = Field(default=1, ge=1, le=3)
    regenerate_profile: bool = Field(default=False, description="Ignore the saved profile and build a new one")
    review_plan: bool = Field(
        default=False,
        description="Pause after research so the author can approve or edit the angle and sources before writing",
    )
    learn_from_results: bool = Field(
        default=True,
        description="Show the writers this brand's best-performing posts, and the planner which topics work",
    )


class PlanDecision(BaseModel):
    """The author's answer when a run pauses for plan review."""

    angle: str | None = Field(default=None, max_length=500, description="Replace the planned angle")
    pillar: str | None = Field(default=None, max_length=200)
    source_urls: list[str] | None = Field(
        default=None, description="Keep only these sources (None = keep all)"
    )
    guidance: str = Field(default="", max_length=1000, description="Extra direction for the writers")


ImageStyle = Literal["photo", "illustration", "3d", "minimal"]


class ImagePrompt(BaseModel):
    """What the art director hands to the image model."""

    prompt: str = Field(description="A vivid, specific image prompt. Never ask for text, letters or logos in the image.")
    alt_text: str = Field(description="Accessible description of the image, max ~150 characters")


class ImageRequest(BaseModel):
    idea: str = Field(default="", max_length=500, description="Optional: your own idea for the image")
    style: ImageStyle | None = Field(default=None, description="Optional visual style preset")


class DraftImageOut(BaseModel):
    id: str
    draft_id: str
    url: str = Field(description="Path to fetch the image from this API, e.g. /media/images/<id>.png")
    prompt: str
    alt_text: str
    aspect_ratio: str
    style: str | None
    model: str
    created_at: datetime


PublicationStatus = Literal["scheduled", "publishing", "published", "failed", "cancelled"]
PUBLISHABLE = ("linkedin", "x", "threads", "instagram")


class Metrics(BaseModel):
    """Normalised post numbers. `shares` folds in reposts and quotes; `saves` folds in bookmarks."""

    views: int | None = None
    reach: int | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0


def interactions_of(m: Metrics) -> int:
    return m.likes + m.comments + m.shares + m.saves


class MetricsOut(Metrics):
    interactions: int = 0
    engagement_rate: float | None = Field(default=None, description="interactions / views, when views are known")

    @classmethod
    def of(cls, m: "Metrics | dict | None") -> "MetricsOut | None":
        if m is None:
            return None
        m = Metrics.model_validate(m)
        total = interactions_of(m)
        rate = round(total / m.views, 4) if m.views else None
        return cls(**m.model_dump(), interactions=total, engagement_rate=rate)


class PublicationOut(BaseModel):
    id: str
    draft_id: str
    account_id: str | None
    account_name: str | None
    platform: PlatformId
    status: PublicationStatus
    scheduled_at: datetime
    published_at: datetime | None
    external_url: str | None
    error: str | None
    attempts: int
    include_image: bool
    metrics: "MetricsOut | None" = None
    metrics_updated_at: datetime | None = None
    metrics_error: str | None = None


class DraftRef(BaseModel):
    id: str
    status: DraftStatus
    review: Review | None = Field(default=None, description="Review of this draft alone, after a rewrite")
    lint: list[str] = Field(default_factory=list, description="Hard-rule problems in the current content")
    images: list[DraftImageOut] = Field(default_factory=list, description="Generated images, newest first")
    publications: list[PublicationOut] = Field(default_factory=list, description="Scheduled and published posts")


class StoredPlatformResult(PlatformResult):
    drafts: list[DraftRef] = Field(default_factory=list, description="Ids for each item, same order")


class RunSummary(BaseModel):
    id: str
    brand_id: str
    status: RunStatus
    platforms: list[PlatformId]
    topic: str
    angle: str | None
    approved: int = Field(description="Platforms the reviewer approved")
    created_at: datetime
    finished_at: datetime | None


class RunDetail(RunSummary):
    variants: int
    error: str | None
    brand_profile: BrandProfile | None
    plan: ContentPlan | None
    sources: list[Source]
    results: list[StoredPlatformResult]



# ---------------------------------------------------------------------------
# Draft editing
# ---------------------------------------------------------------------------


class DraftOut(BaseModel):
    id: str
    run_id: str
    platform: PlatformId
    position: int
    content: dict
    text: str
    status: DraftStatus
    review: Review | None
    lint: list[str] = Field(description="Hard-rule problems in the current content (e.g. too long)")
    updated_at: datetime


class DraftUpdate(BaseModel):
    content: dict | None = Field(default=None, description="Full platform content; validated against the platform")
    status: DraftStatus | None = None


REWRITE_PRESETS = {
    "shorter": "Make it noticeably shorter and tighter without losing the core insight.",
    "punchier": "Make it punchier: a sharper hook, stronger verbs, shorter sentences.",
    "data": "Make it more data-driven: lean on specific facts and numbers from the research.",
    "personal": "Make it more personal: add a first-person story or lesson learned.",
    "simpler": "Use simpler language a non-expert would understand.",
}


class RewriteRequest(BaseModel):
    preset: Literal["shorter", "punchier", "data", "personal", "simpler"] | None = None
    instruction: str = Field(default="", max_length=500, description="Free-text request, e.g. 'mention our launch'")
    fresh: bool = Field(default=False, description="Write a brand-new draft instead of editing this one")

    def text(self) -> str:
        parts = [REWRITE_PRESETS[self.preset]] if self.preset else []
        if self.instruction.strip():
            parts.append(self.instruction.strip())
        return " ".join(parts)


class DraftVersionOut(BaseModel):
    id: str
    source: str = Field(description="generated | edited | rewrite | regenerate | restored")
    note: str | None
    text: str
    created_at: datetime



# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=200, description="At least 10 characters")


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Connections & publishing
# ---------------------------------------------------------------------------


class ConnectionOut(BaseModel):
    id: str
    platform: PlatformId
    display_name: str
    username: str | None
    expires_at: datetime | None
    created_at: datetime


class PlatformConnectInfo(BaseModel):
    platform: PlatformId
    available: bool = Field(description="True when this server has app credentials (or demo mode) for the platform")
    note: str


class ConnectionsOut(BaseModel):
    accounts: list[ConnectionOut]
    platforms: list[PlatformConnectInfo]


class PublishRequest(BaseModel):
    account_id: str
    scheduled_at: datetime | None = Field(default=None, description="UTC time to publish. Empty = publish now.")
    include_image: bool = Field(default=True, description="Attach the draft's newest image where the platform supports it")


class RescheduleRequest(BaseModel):
    scheduled_at: datetime


class ManualMetricsRequest(BaseModel):
    """Numbers typed in by the user (for platforms or posts without an analytics API)."""

    views: int | None = Field(default=None, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)


class ManualPublicationRequest(BaseModel):
    """"I posted this myself" (e.g. Medium, YouTube Shorts), so its results can be tracked."""

    url: str | None = Field(default=None, max_length=2000)
    published_at: datetime | None = None


class MetricsSnapshot(MetricsOut):
    captured_at: datetime
    source: Literal["api", "manual"]


class AnalyticsPost(BaseModel):
    publication_id: str
    draft_id: str
    run_id: str
    brand_id: str
    brand_name: str
    platform: PlatformId
    pillar: str | None
    angle: str | None
    preview: str
    published_at: datetime
    external_url: str | None
    metrics: MetricsOut | None
    metrics_updated_at: datetime | None
    metrics_error: str | None


RunRequest.model_rebuild()
