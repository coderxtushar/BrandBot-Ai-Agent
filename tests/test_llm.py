"""Gemini client behaviour that doesn't need the network: retries and quota errors."""

import pytest
from langchain_core.exceptions import ModelRateLimitError

from backend.config import Settings
from backend.services.llm import GeminiClient, QuotaExhausted, call_with_retry


def failing(*errors, result="ok"):
    calls = []

    async def call():
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result

    return call, calls


async def test_transient_errors_are_retried_once():
    call, calls = failing(RuntimeError("connection reset"))
    assert await call_with_retry(call) == "ok" and len(calls) == 2

    call, calls = failing(RuntimeError("a"), RuntimeError("b"))
    with pytest.raises(RuntimeError, match="b"):
        await call_with_retry(call)
    assert len(calls) == 2


async def test_quota_errors_stop_at_once_and_say_what_happened():
    daily = ModelRateLimitError("429 RESOURCE_EXHAUSTED. Generate content requests per day limit exceeded on Free Tier")
    call, calls = failing(daily)
    with pytest.raises(QuotaExhausted, match="daily free limit"):
        await call_with_retry(call)
    assert len(calls) == 1

    call, _ = failing(ModelRateLimitError("429 RESOURCE_EXHAUSTED. requests per minute"))
    with pytest.raises(QuotaExhausted, match="Wait a minute"):
        await call_with_retry(call)


@pytest.mark.parametrize("level, expected", [("low", {"thinking_level": "low"}), ("default", None)])
def test_thinking_level_is_configurable(level, expected):
    client = GeminiClient(Settings(_env_file=None, google_api_key="test-key", gemini_thinking_level=level))
    assert all(m.thinking_config == expected and m.max_retries == 1 for m in client._models.values())
