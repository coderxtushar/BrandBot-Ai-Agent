"""Offline fakes for the LLM and search services (used by tests and DEMO_MODE)."""

import asyncio

from collections import Counter
from typing import get_args

from backend.schemas import (
    BrandProfile,
    CarouselSlide,
    ContentPlan,
    ImagePrompt,
    InstagramPost,
    LinkedInPost,
    MediumArticle,
    Review,
    SearchQuery,
    ShortsBeat,
    Source,
    ThreadsPost,
    VoiceGuide,
    XThread,
    YouTubeShortScript,
)

SAMPLES = {
    BrandProfile: lambda: BrandProfile(
        positioning="Helps analysts turn data into decisions.",
        audience_persona="Junior data scientists who want business impact.",
        voice=VoiceGuide(traits=["clear", "practical"], do=["use examples"], dont=["hype"]),
        pillars=["Data storytelling", "ML mistakes"],
        hashtags=["datascience", "analytics", "machinelearning"],
        visual_style="Clean editorial photography, navy and warm amber accents",
    ),
    ImagePrompt: lambda: ImagePrompt(
        prompt="Overhead shot of a tidy desk, laptop showing a clean chart, soft morning light",
        alt_text="A laptop on a desk showing a chart in morning light",
    ),
    ContentPlan: lambda: ContentPlan(
        angle="Most ML projects fail because of the problem framing, not the model.",
        pillar="ML mistakes",
        queries=[SearchQuery(query="why ML projects fail 2026"), SearchQuery(query="ML framing", topic="news", time_range="month")],
    ),
    LinkedInPost: lambda: LinkedInPost(
        hook="80% of ML projects never ship.",
        body="Here's the uncomfortable reason.\n\nIt's not the model.",
        closing_question="What killed your last project?",
        hashtags=["ml", "datascience", "analytics"],
    ),
    XThread: lambda: XThread(tweets=["Most ML projects die before the model.", "Here's why.", "Frame first."], hashtags=["ml"]),
    ThreadsPost: lambda: ThreadsPost(posts=["Hot take: your model isn't the problem."], topic_tag="DataScience"),
    InstagramPost: lambda: InstagramPost(
        caption="Your model isn't the problem.",
        hashtags=["ml", "data", "ai", "analytics", "python"],
        slides=[CarouselSlide(headline=f"Slide {i}", text="Point") for i in range(1, 5)],
        image_prompt="Minimal desk with laptop showing a chart",
        alt_text="A laptop with a chart",
    ),
    MediumArticle: lambda: MediumArticle(
        title="Why ML Projects Fail",
        subtitle="It's the framing",
        body_markdown="## Intro\n" + "word " * 900,
        tags=["ml", "data"],
    ),
    YouTubeShortScript: lambda: YouTubeShortScript(
        title="Why your ML project failed",
        hook="Your model is fine.",
        beats=[ShortsBeat(seconds=f"{i*5}-{i*5+5}", voiceover="Short line here.", on_screen_text="Text", visual="Face cam") for i in range(4)],
        cta="Follow for more",
        description="ML framing tips",
        hashtags=["ml", "shorts", "data"],
    ),
}


def _mark(item, tag: str):
    """Visibly change the first text field so rewrites are observable in tests and demo mode."""
    for name, value in item:
        if isinstance(value, str):
            return item.model_copy(update={name: f"{value} [{tag}]"})
        if isinstance(value, list) and value and isinstance(value[0], str):
            return item.model_copy(update={name: [f"{value[0]} [{tag}]", *value[1:]]})
    return item


class FakeLLM:
    """Returns canned objects.

    reject_first_review: reviewer rejects the first review per platform.
    long_first_tweet: the first X draft violates the 280-char limit (exercises the lint path).
    fail_platforms: content model names whose writer raises.
    """

    def __init__(self, reject_first_review=False, long_first_tweet=False, fail_platforms=(), delay=0.0):
        self.delay = delay
        self.calls = Counter()
        self.prompts: list[tuple[str, str, str]] = []
        self.reject_first_review = reject_first_review
        self.long_first_tweet = long_first_tweet
        self.fail_platforms = set(fail_platforms)
        self._reviews = Counter()

    async def structured(self, schema, system, user, *, role="writer"):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.calls[schema.__name__] += 1
        self.prompts.append((schema.__name__, system, user))

        if schema is Review:
            key = system.split(" for ")[1].split(".")[0]  # platform label
            self._reviews[key] += 1
            if self.reject_first_review and self._reviews[key] == 1:
                return Review(approved=False, score=4, issues=["Hook is too generic."])
            return Review(approved=True, score=9, issues=[])

        if schema in SAMPLES:
            return SAMPLES[schema]()

        # Dynamic "<Model>Drafts" wrapper with an `items` list.
        inner = get_args(schema.model_fields["items"].annotation)[0]
        if inner.__name__ in self.fail_platforms:
            raise RuntimeError("boom")
        item = SAMPLES[inner]()
        if inner is XThread and self.long_first_tweet and self.calls[schema.__name__] == 1:
            item = XThread(tweets=["x" * 400])
        if "The author asked for this change" in user:
            item = _mark(item, "rewritten")
        elif "Direction from the author" in user:
            item = _mark(item, "guided")
        return schema(items=[item, SAMPLES[inner](), SAMPLES[inner]()])


class FakeSearcher:
    def __init__(self, delay=0.0):
        self.delay = delay
        self.queries = []

    async def search(self, query):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.queries.append(query.query)
        return [
            Source(title="Study", url="https://example.com/a", snippet="85% of AI projects fail."),
            Source(title=f"Result for {query.query}", url=f"https://example.com/{len(self.queries)}", snippet="..."),
        ]
