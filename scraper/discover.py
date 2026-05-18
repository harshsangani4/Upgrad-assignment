from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from .seeds import CATEGORY_INDEX_URLS, SITEMAP_URL

load_dotenv()

SLUG_URL_RE = re.compile(r"^https://www\.upgrad\.com/([a-z0-9-]+)/$")

NON_COURSE_SLUGS = {
    # chrome / legal / marketing
    "about", "about-us", "blog", "careers", "contact", "contact-us",
    "press", "sitemap", "html-sitemap",
    "privacy", "privacy-policy", "terms", "terms-of-use", "terms-and-conditions", "refund-policy",
    "login", "signup", "register", "auth", "account",
    "us", "sg", "ae", "au", "in", "uk",
    # navigation hubs / category-ish pages
    "courses", "programs", "scholarships", "free-courses", "free-resources",
    "free-masterclass", "events", "webinars", "podcasts", "newsroom", "faq", "help",
    "tutorials", "study-abroad", "success-stories", "placement-support",
    "experience-centers", "offline-centres",
    "partner-with-us", "hire-from-upgrad", "for-business", "for-enterprise",
    "for-college-students", "internzip", "recruit",
    "refer-and-earn", "refer-earn-terms", "report-a-vulnerability",
    "profile-perfect-program-upgrad", "learn",
    "bachelor", "masters", "degree", "certification",
    # plural hub pages (single-segment) that aren't a specific course
    "iit-iim-online-courses", "digital-marketing-courses", "machine-learning-courses",
    "doctor-of-business-administration-dba-courses",
    "gen-ai-and-agentic-ai-programs",
}

NON_COURSE_PATTERNS = (
    re.compile(r"^upskill-to-"),
    re.compile(r"-outcome$"),
)


@dataclass(frozen=True)
class CourseURL:
    url: str
    slug: str
    category_hint: str | None = None


def _normalize(href: str) -> str | None:
    """Strip fragment/query, ensure trailing slash on the path, return canonical absolute URL."""
    try:
        parsed = urlparse(href)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc != "www.upgrad.com":
        return None
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return f"https://www.upgrad.com{path}"


def _slug_from_url(url: str) -> str | None:
    m = SLUG_URL_RE.match(url)
    return m.group(1) if m else None


def _is_course_url(url: str) -> tuple[bool, str | None]:
    slug = _slug_from_url(url)
    if not slug:
        return False, None
    if slug in NON_COURSE_SLUGS:
        return False, None
    if url in CATEGORY_INDEX_URLS:
        return False, None
    if any(p.search(slug) for p in NON_COURSE_PATTERNS):
        return False, None
    return True, slug


def proxy_for_httpx() -> str | None:
    return os.getenv("PROXY_URL") or None


def proxy_for_playwright() -> dict | None:
    p = os.getenv("PROXY_URL")
    return {"server": p} if p else None


def _httpx_client() -> httpx.Client:
    kwargs: dict = {"headers": {"Accept-Language": "en-IN"}, "timeout": 30.0, "follow_redirects": True}
    proxy = proxy_for_httpx()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def _from_sitemap(client: httpx.Client) -> dict[str, CourseURL]:
    out: dict[str, CourseURL] = {}
    try:
        r = client.get(SITEMAP_URL)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] sitemap fetch failed: {e}")
        return out

    locs = re.findall(r"<loc>([^<]+)</loc>", r.text)
    sub_sitemaps = [l for l in locs if l.endswith(".xml")]
    candidates: list[str] = [l for l in locs if not l.endswith(".xml")]

    for sub in sub_sitemaps:
        try:
            sr = client.get(sub)
            sr.raise_for_status()
            candidates.extend(re.findall(r"<loc>([^<]+)</loc>", sr.text))
        except Exception as e:
            print(f"[warn] sub-sitemap {sub} failed: {e}")
            continue

    for raw in candidates:
        norm = _normalize(raw)
        if not norm:
            continue
        ok, slug = _is_course_url(norm)
        if not ok:
            continue
        out[slug] = CourseURL(url=norm, slug=slug, category_hint=None)
    return out


def _from_category(page, category_url: str) -> list[CourseURL]:
    page.goto(category_url, wait_until="domcontentloaded", timeout=60_000)
    # scroll to trigger lazy-loaded carousels of course cards
    last_height = 0
    for _ in range(12):
        h = page.evaluate("document.body.scrollHeight")
        if h == last_height:
            break
        page.evaluate(f"window.scrollTo(0, {h})")
        page.wait_for_timeout(250)
        last_height = h
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass
    hrefs: list[str] = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    found: list[CourseURL] = []
    seen: set[str] = set()
    for raw in hrefs:
        norm = _normalize(raw)
        if not norm:
            continue
        ok, slug = _is_course_url(norm)
        if not ok or slug in seen:
            continue
        seen.add(slug)
        found.append(CourseURL(url=norm, slug=slug, category_hint=category_url))
    return found


def discover() -> list[CourseURL]:
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    rate_limit = float(os.getenv("SCRAPE_RATE_LIMIT_RPS", "1") or "1")
    sleep_between = 1.0 / rate_limit if rate_limit > 0 else 0.0

    by_slug: dict[str, CourseURL] = {}

    with _httpx_client() as client:
        by_slug.update(_from_sitemap(client))

    with sync_playwright() as p:
        launch_kwargs: dict = {"headless": headless}
        pw_proxy = proxy_for_playwright()
        if pw_proxy:
            launch_kwargs["proxy"] = pw_proxy
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            extra_http_headers={"Accept-Language": "en-IN"},
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        for i, cat in enumerate(CATEGORY_INDEX_URLS):
            try:
                for cu in _from_category(page, cat):
                    existing = by_slug.get(cu.slug)
                    if existing is None or existing.category_hint is None:
                        by_slug[cu.slug] = cu
            except Exception as e:
                print(f"[warn] category {cat} failed: {e}")
            if i < len(CATEGORY_INDEX_URLS) - 1:
                time.sleep(sleep_between)
        browser.close()

    return sorted(by_slug.values(), key=lambda c: c.slug)


def main() -> None:
    urls = discover()
    for cu in urls:
        cat = cu.category_hint or "-"
        print(f"{cu.slug}\t{cu.url}\t{cat}")
    print(f"\nTotal unique URLs: {len(urls)}")


if __name__ == "__main__":
    main()
