"""LLM access behind a tiny interface so the graph can be tested with a fake."""

from typing import Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.config import Settings

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    async def structured(
        self, schema: type[T], system: str, user: str, *, role: str = "writer"
    ) -> T:
        """Return an instance of `schema` generated from the prompts.

        `role` lets implementations route to different models ("writer" | "reviewer").
        """
        ...


class QuotaExhausted(RuntimeError):
    """The model provider refused for quota: retrying now only makes the user wait longer."""


def quota_message(exc: Exception) -> str:
    text = str(exc)
    if "per day" in text or "PerDay" in text:
        return (
            "Gemini's daily free limit for this model is used up (the free tier allows only a few runs a day). "
            "It resets at midnight Pacific time, or turn on billing for the Google project that owns GOOGLE_API_KEY."
        )
    return "Gemini is rate limiting this key right now. Wait a minute and try again."


async def call_with_retry(call, attempts: int = 2):
    """Retry transient model errors, but stop at once on quota errors (they'd only fail again, slower)."""
    from langchain_core.exceptions import ModelRateLimitError

    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except ModelRateLimitError as exc:
            raise QuotaExhausted(quota_message(exc)) from exc
        except Exception:
            if attempt == attempts:
                raise


class GeminiClient:
    def __init__(self, settings: Settings):
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")

        # max_retries=1: no retries inside the SDK (it would retry quota errors with back-off); call_with_retry decides.
        common = {"google_api_key": settings.google_api_key, "max_retries": 1}
        if settings.gemini_thinking_level != "default":
            # Gemini 3 thinks at "high" by default: ~35 s per call. "low" is ~20 s and plenty for writing and reviewing.
            common["thinking_config"] = {"thinking_level": settings.gemini_thinking_level}
        self._models = {
            "writer": ChatGoogleGenerativeAI(
                model=settings.gemini_model, temperature=settings.temperature, **common
            ),
            "reviewer": ChatGoogleGenerativeAI(
                model=settings.gemini_review_model, temperature=0.2, **common
            ),
        }

    async def structured(self, schema, system, user, *, role="writer"):
        model = self._models.get(role, self._models["writer"]).with_structured_output(schema)
        result = await call_with_retry(lambda: model.ainvoke([SystemMessage(system), HumanMessage(user)]))
        if result is None:
            raise RuntimeError(f"Model returned no parsable {schema.__name__}")
        return result
