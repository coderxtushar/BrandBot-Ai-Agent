"""Platform specifications.

A spec tells the writer *how* to write for a platform, lets us check hard rules
(character limits etc.) without an LLM, and renders copy-ready text.
Adding a new platform = adding one PlatformSpec here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from pydantic import BaseModel, Field, create_model

from backend.schemas import (
    InstagramPost,
    LinkedInPost,
    MediumArticle,
    PlatformId,
    ThreadsPost,
    XThread,
    YouTubeShortScript,
)


def _tags(tags: list[str]) -> str:
    return " ".join(f"#{t.lstrip('#').replace(' ', '')}" for t in tags if t.strip())


@dataclass(frozen=True)
class PlatformSpec:
    id: PlatformId
    label: str
    content_model: type[BaseModel]
    max_variants: int
    image_aspect: str  # aspect ratio for generated visuals, e.g. "4:5"
    image_role: str    # what the image is for, guides the art director
    style_guide: str
    lint: Callable[[BaseModel], list[str]]
    render: Callable[[BaseModel], str]
    # The text actually sent when publishing: one string per post (several for threads).
    post_parts: Callable[[BaseModel], list[str]] = lambda c: []

    @cached_property
    def drafts_model(self) -> type[BaseModel]:
        """Wrapper model the LLM fills: {"items": [content_model, ...]}."""
        return create_model(
            f"{self.content_model.__name__}Drafts",
            items=(list[self.content_model], Field(min_length=1)),
        )


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

def _render_linkedin(p: LinkedInPost) -> str:
    return f"{p.hook}\n\n{p.body}\n\n{p.closing_question}\n\n{_tags(p.hashtags)}".strip()


def _lint_linkedin(p: LinkedInPost) -> list[str]:
    issues = []
    total = len(_render_linkedin(p))
    if total > 3000:
        issues.append(f"Post is {total} characters; LinkedIn's limit is 3000.")
    if len(p.hook) > 210:
        issues.append("Hook is longer than ~210 characters and will be cut off by '...see more'.")
    if not 3 <= len(p.hashtags) <= 5:
        issues.append(f"Use 3-5 hashtags (found {len(p.hashtags)}).")
    return issues


LINKEDIN = PlatformSpec(
    id=PlatformId.LINKEDIN,
    label="LinkedIn",
    content_model=LinkedInPost,
    max_variants=3,
    image_aspect="1:1",
    image_role="a scroll-stopping feed image that sits above a LinkedIn post",
    style_guide=(
        "LinkedIn post, 120-250 words. The hook (first 1-2 lines) must create curiosity or tension "
        "because only ~210 characters show before '...see more'. Short paragraphs of 1-2 sentences "
        "with blank lines between. Share a concrete insight, story or framework, not generic advice. "
        "No emojis unless the brand voice calls for them. End with one open question."
    ),
    lint=_lint_linkedin,
    render=_render_linkedin,
    post_parts=lambda p: [_render_linkedin(p)],
)


# ---------------------------------------------------------------------------
# X (Twitter)
# ---------------------------------------------------------------------------

def _x_parts(t: XThread) -> list[str]:
    tweets = list(t.tweets)
    if t.hashtags and tweets:
        tweets[-1] = f"{tweets[-1]} {_tags(t.hashtags)}"
    n = len(tweets)
    return [f"{i}/{n} {tw}" if i > 1 else tw for i, tw in enumerate(tweets, 1)]


def _render_x(t: XThread) -> str:
    return "\n\n".join(_x_parts(t))


def _lint_x(t: XThread) -> list[str]:
    issues = []
    if not 1 <= len(t.tweets) <= 8:
        issues.append(f"Threads should have 1-8 tweets (found {len(t.tweets)}).")
    for i, tw in enumerate(t.tweets, 1):
        extra = len(_tags(t.hashtags)) + 1 if (i == len(t.tweets) and t.hashtags) else 0
        numbering = 5 if i > 1 else 0  # "2/5 "
        if len(tw) + extra + numbering > 280:
            issues.append(f"Tweet {i} is too long ({len(tw) + extra + numbering}/280 incl. numbering/hashtags).")
    if len(t.hashtags) > 2:
        issues.append("Use at most 2 hashtags on X.")
    return issues


X = PlatformSpec(
    id=PlatformId.X,
    label="X (Twitter)",
    content_model=XThread,
    max_variants=3,
    image_aspect="16:9",
    image_role="a landscape image attached to the first tweet of a thread",
    style_guide=(
        "An X thread of 3-7 tweets (or a single tweet if the idea is small). Tweet 1 is a bold, "
        "specific hook that works on its own. Each tweet is one idea, punchy, under 260 characters. "
        "Plain language, no corporate tone, no hashtags inside tweets. Last tweet summarises and "
        "invites a reply or follow. Do NOT add numbering like '1/' yourself."
    ),
    lint=_lint_x,
    render=_render_x,
    post_parts=_x_parts,
)


# ---------------------------------------------------------------------------
# Threads (Meta)
# ---------------------------------------------------------------------------

def _threads_parts(t: ThreadsPost) -> list[str]:
    posts = list(t.posts)
    tag = f" #{t.topic_tag.lstrip('#').replace(' ', '')}" if t.topic_tag else ""
    if tag and posts and len(posts[-1]) + len(tag) <= 500:
        posts[-1] += tag
    return posts


def _render_threads(t: ThreadsPost) -> str:
    text = "\n\n---\n\n".join(t.posts)
    return f"{text}\n\n#{t.topic_tag}" if t.topic_tag else text


def _lint_threads(t: ThreadsPost) -> list[str]:
    issues = []
    if not 1 <= len(t.posts) <= 5:
        issues.append(f"Use 1-5 posts (found {len(t.posts)}).")
    for i, p in enumerate(t.posts, 1):
        if len(p) > 500:
            issues.append(f"Post {i} is {len(p)} characters; Threads' limit is 500.")
    return issues


THREADS = PlatformSpec(
    id=PlatformId.THREADS,
    label="Threads",
    content_model=ThreadsPost,
    max_variants=3,
    image_aspect="4:5",
    image_role="a casual, authentic-looking image for a Threads post",
    style_guide=(
        "Threads is conversational and casual, closer to talking than publishing. 1-3 short posts, "
        "each under 450 characters. Opinionated, warm, a bit personal. Ask a genuine question to "
        "start a conversation. At most one topic tag, no hashtag lists."
    ),
    lint=_lint_threads,
    render=_render_threads,
    post_parts=_threads_parts,
)


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------

def _instagram_caption(p: InstagramPost) -> list[str]:
    return [f"{p.caption}\n\n{_tags(p.hashtags)}".strip()]


def _render_instagram(p: InstagramPost) -> str:
    slides = "\n".join(f"Slide {i}: {s.headline} — {s.text}" for i, s in enumerate(p.slides, 1))
    return f"{p.caption}\n\n{_tags(p.hashtags)}\n\n[Carousel]\n{slides}"


def _lint_instagram(p: InstagramPost) -> list[str]:
    issues = []
    if len(p.caption) > 2200:
        issues.append(f"Caption is {len(p.caption)} characters; Instagram's limit is 2200.")
    if len(p.hashtags) > 30:
        issues.append("Instagram allows at most 30 hashtags.")
    if not 3 <= len(p.slides) <= 10:
        issues.append(f"Carousels need 3-10 slides (found {len(p.slides)}).")
    for i, s in enumerate(p.slides, 1):
        if len(s.headline.split()) > 10:
            issues.append(f"Slide {i} headline is too long to read on a phone.")
    return issues


INSTAGRAM = PlatformSpec(
    id=PlatformId.INSTAGRAM,
    label="Instagram",
    content_model=InstagramPost,
    max_variants=2,
    image_aspect="4:5",
    image_role="the cover image (slide 1 background) of an Instagram carousel",
    style_guide=(
        "An Instagram carousel post. Slides teach one idea step by step: slide 1 is a scroll-stopping "
        "promise, middle slides deliver value (one point each, very little text), last slide is a "
        "save/share/follow CTA. Caption: hook line, 2-4 short paragraphs of context, CTA. "
        "Write an image_prompt for a clean, on-brand cover visual (no text in the image)."
    ),
    lint=_lint_instagram,
    render=_render_instagram,
    post_parts=_instagram_caption,
)


# ---------------------------------------------------------------------------
# Medium
# ---------------------------------------------------------------------------

def _render_medium(a: MediumArticle) -> str:
    return f"# {a.title}\n\n_{a.subtitle}_\n\n{a.body_markdown}\n\nTags: {', '.join(a.tags)}"


def _lint_medium(a: MediumArticle) -> list[str]:
    issues = []
    words = len(a.body_markdown.split())
    if words < 600:
        issues.append(f"Article is only {words} words; aim for 800-1500.")
    if words > 2500:
        issues.append(f"Article is {words} words; trim to under 1500-2000.")
    if "## " not in a.body_markdown:
        issues.append("Add ## section headings so the article is skimmable.")
    if len(a.tags) > 5:
        issues.append("Medium allows at most 5 tags.")
    if len(a.title) > 100:
        issues.append("Title is too long; keep it under ~100 characters.")
    return issues


MEDIUM = PlatformSpec(
    id=PlatformId.MEDIUM,
    label="Medium",
    content_model=MediumArticle,
    max_variants=1,
    image_aspect="16:9",
    image_role="the header image at the top of a Medium article",
    style_guide=(
        "A Medium article of 800-1500 words in Markdown. Specific, benefit-driven title and a subtitle "
        "that adds context. Open with a short story or a surprising fact, not a definition. Use ## "
        "headings, short paragraphs, and concrete examples. Cite research inline as Markdown links "
        "using the source URLs provided. End with a clear takeaway."
    ),
    lint=_lint_medium,
    render=_render_medium,
)


# ---------------------------------------------------------------------------
# YouTube Shorts
# ---------------------------------------------------------------------------

def _render_shorts(s: YouTubeShortScript) -> str:
    beats = "\n".join(
        f"[{b.seconds}s] VO: {b.voiceover}\n        TEXT: {b.on_screen_text}\n        VISUAL: {b.visual}"
        for b in s.beats
    )
    return (
        f"TITLE: {s.title}\n\nHOOK (0-2s): {s.hook}\n\n{beats}\n\nCTA: {s.cta}\n\n"
        f"DESCRIPTION:\n{s.description}\n\n{_tags(s.hashtags)}"
    )


def _lint_shorts(s: YouTubeShortScript) -> list[str]:
    issues = []
    if len(s.title) > 100:
        issues.append("Title exceeds YouTube's 100-character limit.")
    words = len(s.hook.split()) + sum(len(b.voiceover.split()) for b in s.beats)
    if words > 170:
        issues.append(f"Voiceover is {words} words, which is too long for 60 seconds (aim for 80-150).")
    if not 3 <= len(s.beats) <= 10:
        issues.append(f"Use 3-10 beats (found {len(s.beats)}).")
    return issues


YOUTUBE_SHORTS = PlatformSpec(
    id=PlatformId.YOUTUBE_SHORTS,
    label="YouTube Shorts",
    content_model=YouTubeShortScript,
    max_variants=2,
    image_aspect="9:16",
    image_role="a vertical YouTube Shorts thumbnail (the title is overlaid separately)",
    style_guide=(
        "A 30-60 second vertical video script. The hook in the first 2 seconds must stop the scroll "
        "(a bold claim, a surprising number or a question). Fast pacing: one idea per beat, 3-6 seconds "
        "each. Spoken language, 80-150 words of voiceover total. On-screen text reinforces each beat in "
        "very few words. End with a CTA (follow, comment, or watch the next one)."
    ),
    lint=_lint_shorts,
    render=_render_shorts,
)


PLATFORMS: dict[PlatformId, PlatformSpec] = {
    s.id: s for s in (LINKEDIN, X, THREADS, INSTAGRAM, MEDIUM, YOUTUBE_SHORTS)
}


def get_spec(platform: PlatformId | str) -> PlatformSpec:
    return PLATFORMS[PlatformId(platform)]
