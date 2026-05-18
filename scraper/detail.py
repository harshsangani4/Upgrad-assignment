from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from .discover import proxy_for_playwright

load_dotenv()

RAW_DIR = Path("data/raw")
SLUG_FROM_URL_RE = re.compile(r"https?://www\.upgrad\.com/([a-z0-9-]+)/?")


@dataclass
class DetailResult:
    slug: str
    url: str
    html: str
    fetched_at: str
    html_path: Path


def _slug_from(url: str) -> str:
    m = SLUG_FROM_URL_RE.match(url.rstrip("/") + "/")
    if not m:
        raise ValueError(f"could not derive slug from {url!r}")
    return m.group(1)


def _expand_all_accordions(page: Page) -> None:
    """Click every collapsed accordion-style trigger so syllabus + FAQ content is in the DOM."""
    # Loop until no more collapsed sections remain (capped to avoid infinite loops).
    for _ in range(8):
        triggers = page.locator("[aria-expanded='false']")
        n = triggers.count()
        if n == 0:
            break
        for i in range(n):
            try:
                triggers.nth(i).scroll_into_view_if_needed(timeout=2_000)
                triggers.nth(i).click(timeout=2_000)
            except Exception:
                continue
        page.wait_for_timeout(300)


def _scroll_through_page(page: Page) -> None:
    """Scroll bottom-ward in chunks so lazy-loaded sections (faculty, testimonials) render."""
    last_height = 0
    for _ in range(20):
        height = page.evaluate("document.body.scrollHeight")
        if height == last_height:
            break
        page.evaluate(f"window.scrollTo(0, {height})")
        page.wait_for_timeout(250)
        last_height = height
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(150)


def scrape_detail(url: str, save_html: bool = True) -> DetailResult:
    """Scrape one course URL. Returns a DetailResult; optionally writes HTML to data/raw/<slug>.html."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slug = _slug_from(url)

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
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_selector("text=Eligibility", timeout=20_000)
        except Exception:
            # some pages spell it differently or use a different anchor; continue best-effort
            pass

        _scroll_through_page(page)
        _expand_all_accordions(page)
        _scroll_through_page(page)

        html = page.content()
        fetched_at = datetime.now(timezone.utc).isoformat()
        browser.close()

    html_path = RAW_DIR / f"{slug}.html"
    if save_html:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    return DetailResult(slug=slug, url=url, html=html, fetched_at=fetched_at, html_path=html_path)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Scrape one upGrad course URL into HTML.")
    ap.add_argument("url", help="Full course URL, e.g. https://www.upgrad.com/<slug>/")
    args = ap.parse_args()

    result = scrape_detail(args.url)
    print(f"Saved {len(result.html):,} bytes to {result.html_path} at {result.fetched_at}")


if __name__ == "__main__":
    main()
