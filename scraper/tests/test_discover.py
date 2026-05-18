from scraper.discover import (
    CourseURL,
    _is_course_url,
    _normalize,
    proxy_for_httpx,
    proxy_for_playwright,
)


def test_proxy_for_httpx_unset_returns_none(monkeypatch):
    monkeypatch.delenv("PROXY_URL", raising=False)
    assert proxy_for_httpx() is None


def test_proxy_for_httpx_blank_returns_none(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "")
    assert proxy_for_httpx() is None


def test_proxy_for_httpx_set_returns_url(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://user:pass@in-proxy.example:8080")
    assert proxy_for_httpx() == "http://user:pass@in-proxy.example:8080"


def test_proxy_for_playwright_unset(monkeypatch):
    monkeypatch.delenv("PROXY_URL", raising=False)
    assert proxy_for_playwright() is None


def test_proxy_for_playwright_set(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://in-proxy.example:8080")
    assert proxy_for_playwright() == {"server": "http://in-proxy.example:8080"}


def test_normalize_strips_fragment_and_query():
    assert _normalize("https://www.upgrad.com/foo-course/?ref=hero#syllabus") == "https://www.upgrad.com/foo-course/"


def test_normalize_adds_trailing_slash():
    assert _normalize("https://www.upgrad.com/foo-course") == "https://www.upgrad.com/foo-course/"


def test_normalize_rejects_off_domain():
    assert _normalize("https://example.com/foo/") is None


def test_normalize_rejects_us_subpath():
    # /us/foo/ has two segments — won't match the single-segment slug pattern downstream
    norm = _normalize("https://www.upgrad.com/us/foo-course/")
    ok, _ = _is_course_url(norm) if norm else (False, None)
    assert ok is False


def test_is_course_url_accepts_slug():
    ok, slug = _is_course_url("https://www.upgrad.com/applied-ai-and-agentic-ai-executive-pgp-certification-iiitb/")
    assert ok is True
    assert slug == "applied-ai-and-agentic-ai-executive-pgp-certification-iiitb"


def test_is_course_url_rejects_category_index():
    ok, _ = _is_course_url("https://www.upgrad.com/data-science-course/")
    assert ok is False


def test_is_course_url_rejects_non_course_slug():
    ok, _ = _is_course_url("https://www.upgrad.com/about-us/")
    assert ok is False


def test_courseurl_is_hashable():
    a = CourseURL(url="https://www.upgrad.com/x/", slug="x", category_hint=None)
    b = CourseURL(url="https://www.upgrad.com/x/", slug="x", category_hint=None)
    assert hash(a) == hash(b)
