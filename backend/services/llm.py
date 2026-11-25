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


class GeminiClient:
    def __init__(self, settings: Settings):
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")

        common = {"google_api_key": settings.google_api_key, "max_retries": 2}
        self._models = {
            "writer": ChatGoogleGenerativeAI(
                model=settings.gemini_model, temperature=settings.temperature, **common
            ),
            "reviewer": ChatGoogleGenerativeAI(
                model=settings.gemini_review_model, temperature=0.2, **common
            ),
        }

    async def structured(self, schema, system, user, *, role="writer"):
        model = self._models.get(role, self._models["writer"])
        runnable = model.with_structured_output(schema).with_retry(stop_after_attempt=2)
        result = await runnable.ainvoke([SystemMessage(system), HumanMessage(user)])
        if result is None:
            raise RuntimeError(f"Model returned no parsable {schema.__name__}")
        return result
