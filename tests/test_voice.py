"""Machine-sounding writing is caught in code and sent back to the writer, not just discouraged in the prompt."""

import pytest

from backend.agents.voice import HUMAN_VOICE, ai_tells
from backend.platforms import get_spec
from backend.schemas import LinkedInPost, PlatformId
from backend.services.fakes import FakeLLM
from tests.test_graph import run

# A real draft the app produced, which an AI detector flagged.
TEMPLATED = """Executives don't care if your classification model has an 85% F1-score.

They care about how much a missed fraud case costs versus a blocked customer.

Here is how to map your confusion matrix to executive decision-making inside Tableau:

1. Export validation outputs.

Instead of debating abstract precision and recall metrics, leadership can slide the parameter to pinpoint the exact
threshold that minimizes bottom-line financial loss.

How do you currently translate model evaluation metrics into financial impact for your leadership team?

#datascience #tableau"""

HUMAN = """I shipped a fraud model last spring with a 0.5 threshold because that was the default in our Go service.
Nobody questioned it, including me.

Then finance asked what each missed case cost. Roughly $1,000. A wrongly blocked customer? About $50.

So I moved the threshold to 0.3 and monthly loss dropped by a third. The F1 score got worse. Nobody in the exec
meeting noticed or cared.

What killed your last model in review?

#datascience #fraud"""


def test_templated_post_is_caught_with_each_phrase_quoted():
    issues = " | ".join(ai_tells(TEMPLATED))
    for expected in ("don't care", "Here is how", "Instead of", "'pinpoint'", "'bottom-line'", "engagement question"):
        assert expected in issues, expected


def test_plain_human_writing_passes():
    assert ai_tells(HUMAN) == []  # a specific question at the end is fine


@pytest.mark.parametrize(
    "text",
    [
        "It's not about the model, it's about the data.",
        "We need to leverage our data.",
        "The truth is, nobody reads dashboards.",
        "Ship it — then fix it.",
        "Ultimately, it depends.",
    ],
)
def test_common_tells(text):
    assert ai_tells(text)


def test_linkedin_closing_question_is_optional():
    spec = get_spec(PlatformId.LINKEDIN)
    post = LinkedInPost(hook="I moved one threshold.", body="Loss dropped by a third.", hashtags=["ml", "fraud", "data"])
    assert spec.render(post) == "I moved one threshold.\n\nLoss dropped by a third.\n\n#ml #fraud #data"
    assert "closing_question is optional" in spec.style_guide


async def test_templated_draft_goes_back_to_the_writer_with_the_phrase():
    spec = get_spec(PlatformId.LINKEDIN)

    class TemplatedFirst(FakeLLM):
        async def structured(self, schema, system, user, *, role="writer"):
            if schema is spec.drafts_model and self.calls[schema.__name__] == 0:
                self.calls[schema.__name__] += 1
                self.prompts.append((schema.__name__, system, user))
                bad = LinkedInPost(hook="Here's why your models fail.", body="It's crucial to leverage data.", hashtags=["a", "b", "c"])
                return schema(items=[bad])
            return await super().structured(schema, system, user, role=role)

    llm = TemplatedFirst()
    r = (await run(llm, platforms=[PlatformId.LINKEDIN]))["results"][0]
    assert r.attempts == 2 and r.review.approved
    writer = [(sys_, u) for n, sys_, u in llm.prompts if n == spec.drafts_model.__name__]
    assert HUMAN_VOICE in writer[0][0]
    second_user = writer[1][1]
    assert "Here's why" in second_user and "'leverage'" in second_user
