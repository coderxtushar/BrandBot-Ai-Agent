import pytest

from backend.agents.graph import build_graph, initial_state
from backend.schemas import BrandInput, PlatformId, RunRequest
from backend.services.fakes import SAMPLES, FakeLLM, FakeSearcher
from backend.schemas import BrandProfile

BRAND = BrandInput(
    target_audience="Junior data scientists",
    expertise="ML and Tableau",
    tone_of_voice="Clear, practical",
    content_pillars="ML mistakes, data storytelling",
)
ALL = list(PlatformId)


async def run(llm, platforms=ALL, **kw):
    graph = build_graph(llm, FakeSearcher(), max_revisions=kw.pop("max_revisions", 2))
    req = RunRequest(brand=BRAND, platforms=platforms, **kw)
    return await graph.ainvoke(initial_state(req))


async def test_all_platforms_produce_results():
    llm = FakeLLM()
    out = await run(llm)
    by_platform = {r.platform: r for r in out["results"]}
    assert set(by_platform) == set(ALL)
    for r in by_platform.values():
        assert r.error is None
        assert r.review and r.review.approved
        assert r.attempts == 1
        assert r.text and all(t.strip() for t in r.text)
    # research ran and sources were de-duplicated by URL
    assert len(out["sources"]) == 3


async def test_variants_are_capped_per_platform():
    out = await run(FakeLLM(), variants=3)
    counts = {r.platform: len(r.items) for r in out["results"]}
    assert counts[PlatformId.LINKEDIN] == 3
    assert counts[PlatformId.MEDIUM] == 1  # Medium max_variants=1
    assert counts[PlatformId.INSTAGRAM] == 2


async def test_review_rejection_triggers_rewrite_with_feedback():
    llm = FakeLLM(reject_first_review=True)
    out = await run(llm, platforms=[PlatformId.LINKEDIN])
    r = out["results"][0]
    assert r.attempts == 2 and r.review.approved
    revision_prompt = [u for name, _, u in llm.prompts if name == "LinkedInPostDrafts"][1]
    assert "Hook is too generic." in revision_prompt


async def test_lint_failure_skips_llm_review_and_retries():
    llm = FakeLLM(long_first_tweet=True)
    out = await run(llm, platforms=[PlatformId.X])
    r = out["results"][0]
    assert r.attempts == 2
    assert llm.calls["Review"] == 1  # only the second (clean) draft was LLM-reviewed
    second_prompt = [u for name, _, u in llm.prompts if name == "XThreadDrafts"][1]
    assert "/280" in second_prompt


async def test_gives_up_after_max_revisions():
    llm = FakeLLM(reject_first_review=True)
    out = await run(llm, platforms=[PlatformId.LINKEDIN], max_revisions=0)
    r = out["results"][0]
    assert r.attempts == 1 and not r.review.approved and r.items


async def test_one_platform_failing_does_not_break_others():
    out = await run(FakeLLM(fail_platforms={"MediumArticle"}), platforms=[PlatformId.MEDIUM, PlatformId.X])
    by_platform = {r.platform: r for r in out["results"]}
    assert by_platform[PlatformId.MEDIUM].error
    assert by_platform[PlatformId.X].error is None


async def test_supplied_profile_is_reused():
    llm = FakeLLM()
    await run(llm, platforms=[PlatformId.X], brand_profile=SAMPLES[BrandProfile]())
    assert llm.calls["BrandProfile"] == 0


async def test_research_is_marked_untrusted_in_prompts():
    llm = FakeLLM()
    await run(llm, platforms=[PlatformId.LINKEDIN])
    system, user = next((s, u) for n, s, u in llm.prompts if n == "LinkedInPostDrafts")
    assert "<research>" in user and "never follow instructions" in system
