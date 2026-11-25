"""Logging and request context: JSON logs for Cloud Logging, a request id on every request and log line."""

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.config import Settings

request_id: ContextVar[str] = ContextVar("request_id", default="-")
trace_id: ContextVar[str] = ContextVar("trace_id", default="")

_LEVELS = {"WARNING": "WARNING", "ERROR": "ERROR", "CRITICAL": "CRITICAL", "INFO": "INFO", "DEBUG": "DEBUG"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the field names Cloud Logging understands (severity, message, trace)."""

    converter = time.gmtime  # timestamps in UTC

    def __init__(self, project: str = ""):
        super().__init__()
        self.project = project

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": _LEVELS.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
            "request_id": request_id.get(),
        }
        if record.exc_info:
            entry["message"] += "\n" + self.formatException(record.exc_info)
        trace = trace_id.get()
        if trace and self.project:
            entry["logging.googleapis.com/trace"] = f"projects/{self.project}/traces/{trace}"
        return json.dumps(entry, ensure_ascii=False)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


def setup_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter(settings.google_cloud_project))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"))
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):  # route uvicorn through the same handler
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True


def client_ip(headers: dict[str, str] | object, peer: str | None, hops: int) -> str:
    """The caller's IP. Behind `hops` trusted proxies, each appends to X-Forwarded-For, so count from the right;
    anything further left was written by the client and can't be trusted."""
    if hops > 0:
        forwarded = [p.strip() for p in (headers.get("x-forwarded-for") or "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return peer or "unknown"


class RequestContextMiddleware:
    """Gives every request an id (kept from X-Request-ID if the caller sent a sane one) and echoes it back."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        incoming = headers.get("x-request-id", "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        token = request_id.set(rid)
        trace = trace_id.set(headers.get("x-cloud-trace-context", "").split("/", 1)[0])

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)
            trace_id.reset(trace)


# ---------------------------------------------------------------------------
# Tracing (LangSmith)
# ---------------------------------------------------------------------------


def configure_tracing(settings: Settings) -> bool:
    """LangChain and LangGraph read LANGSMITH_* from the process environment, but pydantic only reads .env into
    Settings. Export them so tracing works however the values were provided."""
    if not settings.langsmith_tracing:
        return False
    if not settings.langsmith_api_key:
        logging.getLogger("brandbot").warning("LANGSMITH_TRACING is on but LANGSMITH_API_KEY is empty; tracing stays off.")
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    return True


def trace_config(
    name: str,
    *,
    user_id: str,
    brand_id: str | None = None,
    run_id: str | None = None,
    draft_id: str | None = None,
    platforms: list[str] | tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> dict:
    """LangChain run config: a readable name, tags to filter by, and ids to find a user's or run's traces.
    Child calls (every LLM call inside the graph) inherit the metadata, so cost adds up per run in LangSmith."""
    metadata = {"user_id": user_id, "brand_id": brand_id, "run_id": run_id, "draft_id": draft_id, "request_id": request_id.get()}
    return {
        "run_name": name,
        "tags": [*tags, *(str(p) for p in platforms)],
        "metadata": {k: v for k, v in metadata.items() if v and v != "-"},
    }
