import json

import pytest
from fastapi.testclient import TestClient

from backend.agents.graph import build_graph
from backend.api.deps import graph_dep
from backend.db.session import Database, get_database
from backend.main import app
from backend.services.fakes import FakeLLM, FakeSearcher


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(tmp_path, llm):
    """API client backed by a throwaway SQLite DB and the fake LLM/search."""
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    graph = build_graph(llm, FakeSearcher())
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[graph_dep] = lambda: graph
    with TestClient(app) as c:  # runs lifespan -> creates tables
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
