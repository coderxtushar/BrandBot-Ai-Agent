import json
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from backend.agents.checkpoint import make_serde, open_checkpointer
from backend.api.deps import Services, services_dep
from backend.db.session import Database, get_database
from backend.main import app
from backend.services.fakes import FakeLLM, FakeSearcher


@asynccontextmanager
async def memory_checkpointer():
    yield InMemorySaver(serde=make_serde())


def use_services(llm, searcher=None, max_revisions=2):
    """Point the API at these (fake) AI services."""
    services = Services(llm, searcher or FakeSearcher(), max_revisions)
    app.dependency_overrides[services_dep] = lambda: services
    return services


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(tmp_path, llm):
    """API client backed by a throwaway SQLite DB and the fake LLM/search."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[open_checkpointer] = memory_checkpointer
    use_services(llm)
    with TestClient(app) as c:  # runs lifespan -> creates tables + checkpointer
        yield c
    app.dependency_overrides.clear()


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        lines = block.strip().splitlines()
        event = next((l[7:] for l in lines if l.startswith("event: ")), None)
        data = "\n".join(l[6:] for l in lines if l.startswith("data: "))
        if event and data:
            events.append((event, json.loads(data)))
    return events


def stream(client, path, payload) -> list[tuple[str, dict]]:
    with client.stream("POST", path, json=payload) as res:
        assert res.status_code == 200, res.read()
        return parse_sse("".join(res.iter_text()))
