"""Database tables.

brands ─< runs ─< platform_results ─< drafts ─< draft_versions
                                              └─< draft_images

- A brand holds the user's raw input and the generated (or hand-edited) brand profile.
- A run is one generation request: platforms, topic, the plan, sources, and a profile snapshot.
- A platform_result is one platform's outcome inside a run (review, attempts, error).
- A draft is one variant of content for that platform; drafts are what users edit and approve.
- A draft_version is a snapshot of a draft after each change, for history and undo.
- A draft_image is a generated visual for a draft (file in media storage).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, TypeDecorator
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


class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
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
