# Brand Bot API. Builds from the repo root:  docker build -t brandbot-api .
# Cloud Run sets $PORT; locally it defaults to 8080.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy VIRTUAL_ENV=/opt/venv
RUN uv venv /opt/venv
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv uv pip install -r requirements.txt

FROM python:3.12-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    LOG_FORMAT=json
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY backend ./backend
# media/ and SQLite files are only used without GCS/Postgres (e.g. a quick local run); keep them writable.
RUN mkdir -p media /data/media && chown -R app:app /app /data
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2)"
# One process per container; the platform scales containers. Migrations run separately (`alembic upgrade head`),
# or at start with MIGRATE_ON_START=true on single-instance hosts without a pre-deploy step (Render's free plan).
CMD ["sh", "-c", "if [ \"$MIGRATE_ON_START\" = true ]; then alembic upgrade head || exit 1; fi; exec uvicorn backend.main:app --host 0.0.0.0 --port \"$PORT\" --no-access-log --timeout-graceful-shutdown 8"]
