from backend.platforms import PLATFORMS, get_spec
from backend.schemas import LinkedInPost, PlatformId, ThreadsPost, XThread
from backend.services.fakes import SAMPLES


def test_every_platform_has_a_spec():
    assert set(PLATFORMS) == set(PlatformId)


def test_samples_pass_lint_and_render():
    for spec in PLATFORMS.values():
        sample = SAMPLES[spec.content_model]()
        assert spec.lint(sample) == [], spec.id
        assert spec.render(sample).strip()


def test_x_flags_long_tweets_and_numbers_thread():
    spec = get_spec("x")
    assert any("280" in i for i in spec.lint(XThread(tweets=["a" * 300])))
    text = spec.render(XThread(tweets=["hook", "two", "three"], hashtags=["ai"]))
    assert text.startswith("hook") and "2/3 two" in text and text.endswith("#ai")


def test_linkedin_hashtag_count_and_length():
    spec = get_spec("linkedin")
    post = LinkedInPost(hook="h", body="b" * 3100, closing_question="q?", hashtags=["a"])
    issues = spec.lint(post)
    assert any("3000" in i for i in issues) and any("hashtags" in i for i in issues)


def test_threads_char_limit():
    assert get_spec("threads").lint(ThreadsPost(posts=["x" * 501]))


def test_hashtags_are_normalised():
    text = get_spec("linkedin").render(
        LinkedInPost(hook="h", body="b", closing_question="q", hashtags=["#AI", "machine learning", "data"])
    )
    assert "#AI #machinelearning #data" in text
