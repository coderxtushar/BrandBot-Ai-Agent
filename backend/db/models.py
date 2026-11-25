"""Database tables.

users ─< sessions
users ─< platform_accounts ─< publications >─ drafts
                              publications ─< post_metrics
users ─< brands

brands ─< runs ─< platform_results ─< drafts ─< draft_versions
                                              └─< draft_images

- A brand holds the user's raw input and the generated (or hand-edited) brand profile.
- A run is one generation request: platforms, topic, the plan, sources, and a profile snapshot.
- A platform_result is one platform's outcome inside a run (review, attempts, error).
- A draft is one variant of content for that platform; drafts are what users edit and approve.
- A draft_version is a snapshot of a draft after each change, for history and undo.
- A draft_image is a generated visual for a draft (file in media storage).
- rate_limits holds request counters per fixed time window, shared by every API instance.
- media_objects holds image bytes when MEDIA_BACKEND=db (hosts without a persistent disk or a bucket).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every database.

    SQLite has no timezone support and hands back naive datetimes, which the browser would
    then misread as local time. Normalise to UTC on the way in and re-attach it on the way out.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)  # stored lower-cased
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))


class Session(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class OAuthState(Base):
    """One pending "Connect account" round-trip (CSRF state + PKCE verifier)."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(32))
    code_verifier: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PlatformAccount(TimestampMixin, Base):
    """A connected social account. Tokens are encrypted at rest."""

    __tablename__ = "platform_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", "external_id", name="uq_account_per_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text)  # encrypted
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="")


class Publication(TimestampMixin, Base):
    """A draft scheduled for, or published to, a connected account."""

    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|publishing|published|failed|cancelled
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    image_id: Mapped[str | None] = mapped_column(ForeignKey("draft_images.id", ondelete="SET NULL"), nullable=True)
    include_image: Mapped[bool] = mapped_column(Boolean, default=True)
    asset_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # converted copy (e.g. JPEG for Instagram)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # analytics: the newest numbers live here; every reading is also kept in post_metrics
    latest_metrics: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    metrics_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft: Mapped["Draft"] = relationship(back_populates="publications")
    account: Mapped[PlatformAccount | None] = relationship(lazy="selectin")


class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    input: Mapped[dict] = mapped_column(JSONType)
    profile: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    profile_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    runs: Mapped[list["Run"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan", passive_deletes=True
    )


class Run(TimestampMixin, Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    brand_id: Mapped[str] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|completed|failed|cancelled
    platforms: Mapped[list] = mapped_column(JSONType)
    topic: Mapped[str] = mapped_column(Text, default="")
    variants: Mapped[int] = mapped_column(Integer, default=1)
    profile: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # snapshot used for this run
    plan: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    sources: Mapped[list] = mapped_column(JSONType, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    brand: Mapped[Brand] = relationship(back_populates="runs")
    results: Mapped[list["PlatformRun"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlatformRun.position",
        lazy="selectin",
    )


class PlatformRun(Base):
    __tablename__ = "platform_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer, default=0)
    review: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="results")
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="platform_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Draft.position",
        lazy="selectin",
    )


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_result_id: Mapped[str] = mapped_column(
        ForeignKey("platform_results.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[dict] = mapped_column(JSONType)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|rejected
    review: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # set when this draft alone is re-reviewed

    platform_result: Mapped[PlatformRun] = relationship(back_populates="drafts")
    publications: Mapped[list["Publication"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Publication.scheduled_at.desc()",
        lazy="selectin",
    )
    images: Mapped[list["DraftImage"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DraftImage.created_at.desc()",
        lazy="selectin",
    )
    # Never loaded implicitly (history pages would otherwise pull every version). Query explicitly.
    versions: Mapped[list["DraftVersion"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", passive_deletes=True, lazy="raise_on_sql"
    )


class DraftVersion(Base):
    """Every state a draft has been in, newest last. The latest one equals the draft's current content."""

    __tablename__ = "draft_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # generated|edited|rewrite|regenerate|restored
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict] = mapped_column(JSONType)
    text: Mapped[str] = mapped_column(Text)
    review: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    draft: Mapped[Draft] = relationship(back_populates="versions")


class DraftImage(Base):
    """A generated visual for a draft. The file lives in media storage under `storage_key`."""

    __tablename__ = "draft_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str] = mapped_column(Text)
    aspect_ratio: Mapped[str] = mapped_column(String(10))
    style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    draft: Mapped[Draft] = relationship(back_populates="images")


class PostMetric(Base):
    """One reading of a published post's numbers (from the platform, or typed in by the user)."""

    __tablename__ = "post_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    source: Mapped[str] = mapped_column(String(10), default="api")  # api | manual
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    raw: Mapped[dict | None] = mapped_column(JSONType, nullable=True)


class RateLimitCounter(Base):
    """Requests counted in one fixed window, e.g. key 'runs:<user id>:3600:<window number>'."""

    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)  # unix seconds when the window ends


class MediaObject(Base):
    """A stored file (generated image), keyed like 'images/<32 hex>.png'. Used when MEDIA_BACKEND=db."""

    __tablename__ = "media_objects"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
