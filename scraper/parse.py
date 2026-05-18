"""
Pure-function HTML → dict parser for upGrad course pages.

Strategy: JSON-LD (Schema.org `Course`, `BreadcrumbList`, `FAQPage`) is the source
of truth for fields where upGrad publishes it. The page also carries Next.js RSC
payloads with escaped JSON (`\\"label\\":\\"EMI Starts from\\"...`) that we regex
out for the summary card (`infoPointers`) and the syllabus modules. The DOM is
the last resort for things upGrad doesn't structure (tools grid, hiring logos,
faculty cards).

Every field is None-tolerant — upGrad's template often has empty sections.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup, Tag


# ---------- low-level helpers ----------------------------------------------------

def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    t = node.get_text(" ", strip=True)
    return t or None


def _first_match(text: str | None, pattern: str, group: int = 1, flags: int = re.IGNORECASE) -> str | None:
    if not text:
        return None
    m = re.search(pattern, text, flags)
    return m.group(group) if m else None


def _to_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(re.sub(r"[^\d-]", "", s))
    except (ValueError, TypeError):
        return None


def _parse_iso_date(s: str | None) -> str | None:
    """Try several upGrad date formats; return ISO yyyy-mm-dd."""
    if not s:
        return None
    s = s.strip()
    formats = (
        "%d-%b-%y", "%d-%b-%Y",
        "%B %d, %Y", "%b %d, %Y",
        "%Y-%m-%d",
        "%d %B %Y", "%d %b %Y",
        "%m/%d/%Y", "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _unescape_jsonish(s: str) -> str:
    """Best-effort decode of the doubly-escaped JSON Next.js embeds in script tags."""
    return (
        s.replace('\\"', '"')
         .replace("\\u0026", "&")
         .replace("\\u003c", "<")
         .replace("\\u003e", ">")
         .replace("\\/", "/")
    )


# ---------- JSON-LD extraction ---------------------------------------------------

def _iter_json_ld(soup: BeautifulSoup):
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                yield item
        elif isinstance(data, dict):
            yield data


def _find_ld(blocks: list[dict], schema_type: str) -> dict | None:
    for b in blocks:
        if b.get("@type") == schema_type:
            return b
    return None


# ---------- escaped-JSON regex extractors ---------------------------------------

INFO_POINTER_RE = re.compile(
    r'\\"label\\":\\"(?P<label>[^"\\]+)\\"'
    r'(?:,\\"icon\\":\\"[^"\\]*\\")?'
    r',\\"value\\":\\"(?P<value>[^"\\]+)\\"'
    r'|'
    r'\\"label\\":\\"(?P<label2>[^"\\]+)\\"'
    r',\\"icon\\":\\"[^"\\]*\\"'
    r',\\"value\\":\\"(?P<value2>[^"\\]+)\\"'
    r'|'
    r'\\"label\\":\\"(?P<label3>[^"\\]+)\\",\\"value\\":\\"(?P<value3>[^"\\]+)\\"',
    re.IGNORECASE,
)

MODULE_RE = re.compile(
    r'\\"title\\":\\"(?P<title>[^"]{4,200}?)\\"'
    r'[^{}]{0,300}?'
    r'\\"course\\":\\"(?P<course>(?:Module|MODULE)\s*\d+)\\"'
    r'(?:[^{}]{0,300}?\\"noOfWeeks\\":\\"(?P<weeks>\d+)\s*Weeks?\\")?'
    r'(?:[^{}]{0,300}?\\"description\\":\\"(?P<description>[^"]{0,400}?)\\")?',
    re.IGNORECASE | re.DOTALL,
)


FACULTY_RE = re.compile(
    r'\\"name\\":\\"(?P<name>(?:Dr\.?|Prof\.?|Mr\.?|Ms\.?)[^"]{2,80}?)\\"'
    r'[^{}]{0,200}?'
    r'\\"role\\":\\"(?P<role>[^"]{2,120}?)\\"'
    r'(?:[^{}]{0,400}?\\"profileLink\\":\\"(?P<linkedin>[^"]{0,300}?)\\")?',
    re.DOTALL,
)


def _extract_info_pointers(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in INFO_POINTER_RE.finditer(html):
        label = m.group("label") or m.group("label2") or m.group("label3")
        value = m.group("value") or m.group("value2") or m.group("value3")
        if label and value and label not in out:
            out[label.strip()] = value.strip()
    return out


def _extract_modules_from_embedded(html: str) -> list[dict[str, Any]]:
    seen_titles: set[str] = set()
    modules: list[dict[str, Any]] = []
    for m in MODULE_RE.finditer(html):
        title = _unescape_jsonish(m.group("title")).strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        weeks = int(m.group("weeks")) if m.group("weeks") else None
        description = _unescape_jsonish(m.group("description") or "").strip() or None
        course_label = m.group("course").strip()
        order = _to_int(_first_match(course_label, r"(\d+)"))
        modules.append({
            "name": title,
            "weeks": weeks,
            "topics": [],
            "module_number": order,
            "description": description,
        })
    modules.sort(key=lambda m: m.get("module_number") or 999)
    return modules


# ---------- DOM helpers for fallback fields -------------------------------------

def _section_by_heading(soup: BeautifulSoup, *heading_texts: str) -> Tag | None:
    lowered = [h.lower() for h in heading_texts]
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = (tag.get_text(" ", strip=True) or "").lower()
        if any(h in txt for h in lowered):
            parent = tag.parent
            for _ in range(4):
                if parent is None:
                    break
                if parent.name in ("section", "article", "div"):
                    return parent
                parent = parent.parent
            return tag.parent
    return None


def _extract_hero_logos(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """First two non-chrome img alts under the hero section."""
    hero = soup.find("section", class_=re.compile("hero", re.IGNORECASE)) or soup.find("header") or soup
    alts = []
    for img in hero.find_all("img", alt=True):
        a = (img.get("alt") or "").strip()
        if not a:
            continue
        low = a.lower()
        if "upgrad" in low or "logo" in low or low in {"image", "imagesrc", "arrow-image"}:
            continue
        alts.append(a)
    return (alts[0] if alts else None), (alts[1] if len(alts) > 1 else None)


def _extract_tools(soup: BeautifulSoup) -> list[str]:
    section = _section_by_heading(soup, "Tools")
    if section is None:
        return []
    out = sorted({(i.get("alt") or "").strip() for i in section.find_all("img", alt=True)})
    return [a for a in out if a and a.lower() not in {"image", "imagesrc"}]


def _extract_target_roles(soup: BeautifulSoup) -> list[dict[str, str]]:
    section = _section_by_heading(soup, "Career Outcomes", "Roles", "Target Roles", "Career Impact")
    if section is None:
        return []
    rows: list[dict[str, str]] = []
    for tr in section.find_all("tr"):
        cells = [_text(td) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            rows.append({"role": cells[0], "salary_label": cells[1]})
    return rows


def _extract_industries(soup: BeautifulSoup) -> list[str]:
    section = _section_by_heading(soup, "Industries Hiring", "Industries")
    if section is None:
        return []
    return [t for t in (_text(li) for li in section.find_all("li")) if t]


def _extract_hiring_companies(soup: BeautifulSoup) -> list[str]:
    section = _section_by_heading(soup, "Top Hiring Companies", "Hiring Companies", "Companies")
    if section is None:
        return []
    out = sorted({(i.get("alt") or "").strip() for i in section.find_all("img", alt=True)})
    return [a for a in out if a and a.lower() not in {"image", "imagesrc"}]


def _extract_faculty_from_embedded(html: str) -> list[dict[str, str | None]]:
    """Pull faculty cards out of the Next.js RSC payload (escaped JSON)."""
    seen_names: set[str] = set()
    out: list[dict[str, str | None]] = []
    for m in FACULTY_RE.finditer(html):
        name = _unescape_jsonish(m.group("name")).strip()
        role = _unescape_jsonish(m.group("role")).strip()
        linkedin = _unescape_jsonish(m.group("linkedin") or "").strip() or None
        if not name or name in seen_names:
            continue
        # filter out obvious non-faculty hits (e.g. "Dr." appearing in marketing copy)
        if len(name.split()) > 6 or len(role) > 120:
            continue
        seen_names.add(name)
        out.append({"name": name, "title": role, "linkedin": linkedin})
    return out


def _extract_faculty(soup: BeautifulSoup, html: str) -> list[dict[str, str | None]]:
    embedded = _extract_faculty_from_embedded(html)
    if embedded:
        return embedded
    section = _section_by_heading(soup, "Instructors", "Faculty", "Mentors")
    if section is None:
        return []
    out: list[dict[str, str | None]] = []
    for card in section.find_all(["article", "div"], recursive=True):
        name_node = card.find(["h3", "h4", "h5"])
        name = _text(name_node)
        if not name or len(name.split()) > 6:
            continue
        title_node = name_node.find_next_sibling(["p", "span", "div"]) if name_node else None
        title = _text(title_node)
        linkedin = None
        a = card.find("a", href=re.compile(r"linkedin\.com", re.IGNORECASE))
        if a and a.get("href"):
            linkedin = a["href"]
        out.append({"name": name, "title": title, "linkedin": linkedin})
    seen, deduped = set(), []
    for f in out:
        if f["name"] in seen:
            continue
        seen.add(f["name"])
        deduped.append(f)
    return deduped


def _extract_certificates(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    section = _section_by_heading(soup, "Certificate")
    if section is None:
        return []
    out: list[dict[str, str | None]] = []
    for img in section.find_all("img", alt=True):
        alt = (img.get("alt") or "").strip()
        if not alt or alt.lower() in {"image", "imagesrc"}:
            continue
        out.append({"issuer": None, "name": alt})
    return out


def _extract_key_highlights(soup: BeautifulSoup) -> list[str]:
    section = _section_by_heading(soup, "Key Highlights", "Highlights")
    if section is None:
        return []
    return [t for t in (_text(li) for li in section.find_all("li")) if t]


def _extract_testimonials(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    section = _section_by_heading(soup, "Testimonials", "Alumni", "Reviews", "Class Profile")
    if section is None:
        return []
    out: list[dict[str, str | None]] = []
    for card in section.find_all(["article", "div"]):
        quote_node = card.find(["blockquote", "p"])
        quote = _text(quote_node)
        if not quote or len(quote) < 30:
            continue
        name_node = card.find(["h3", "h4", "h5", "strong"])
        name = _text(name_node)
        role_node = name_node.find_next_sibling(["p", "span"]) if name_node else None
        role = _text(role_node)
        yoe = _first_match(role or "", r"(\d+)\+?\s*yrs?")
        out.append({"name": name, "role": role, "quote": quote, "yoe": yoe})
    return out


def _extract_eligibility(soup: BeautifulSoup) -> tuple[str | None, int | None, str | None]:
    section = _section_by_heading(soup, "Eligibility")
    raw = _text(section)
    if not raw:
        body = soup.get_text(" ", strip=True)
        m = re.search(r"(Bachelor'?s[^.]{0,200}aggregate[^.]{0,50})", body, re.IGNORECASE)
        raw = m.group(1) if m else None
    if not raw:
        return None, None, None
    marks = _to_int(_first_match(raw, r"(\d{2})%\s*aggregate"))
    degree = None
    for candidate in ("Master's", "Masters", "Bachelor's", "Bachelors", "Diploma", "12th"):
        if re.search(rf"\b{re.escape(candidate)}\b", raw, re.IGNORECASE):
            degree = candidate.replace("Bachelors", "Bachelor's").replace("Masters", "Master's")
            break
    return raw, marks, degree


# ---------- top-level entry point -----------------------------------------------

def parse(html: str, slug: str, url: str | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    ld_blocks = list(_iter_json_ld(soup))

    course_ld = _find_ld(ld_blocks, "Course") or {}
    bc_ld = _find_ld(ld_blocks, "BreadcrumbList") or {}
    faq_ld = _find_ld(ld_blocks, "FAQPage") or {}

    # Title
    title = course_ld.get("name") or _text(soup.find("h1")) or _text(soup.find("h2"))

    # Provider: prefer CourseInstance.location, else first non-upgrad hero img alt
    provider: str | None = None
    instances = course_ld.get("hasCourseInstance") or []
    if isinstance(instances, dict):
        instances = [instances]
    if instances and isinstance(instances[0], dict):
        loc = instances[0].get("location")
        if isinstance(loc, str):
            provider = loc.strip()
    hero_provider, hero_co_brand = _extract_hero_logos(soup)
    if not provider:
        provider = hero_provider
    co_brand = hero_co_brand if hero_co_brand and hero_co_brand != provider else None
    if not co_brand and provider and hero_provider and hero_provider != provider:
        co_brand = hero_provider

    # Fee from JSON-LD
    fee_inr_total: int | None = None
    fee_usd_total: int | None = None
    cred = course_ld.get("educationalCredentialAwarded") or {}
    if isinstance(cred, list) and cred:
        cred = cred[0]
    offers = (cred or {}).get("offers") if isinstance(cred, dict) else None
    if isinstance(offers, dict):
        price = offers.get("price")
        currency = (offers.get("priceCurrency") or "").upper()
        if price is not None:
            price_int = _to_int(str(price))
            if currency == "INR":
                fee_inr_total = price_int
            elif currency == "USD":
                fee_usd_total = price_int

    # infoPointers (summary card)
    info = _extract_info_pointers(html)
    duration_label = info.get("Duration")
    duration_weeks = _to_int(_first_match(duration_label or "", r"(\d+)\s*Weeks"))
    if duration_weeks is None:
        months = _to_int(_first_match(duration_label or "", r"(\d+)\s*Months?"))
        if months is not None:
            duration_weeks = int(round(months * 4.345))

    emi = _to_int(_first_match(info.get("EMI Starts from", ""), r"(\d[\d,]*)"))
    if emi is None:
        emi = _to_int(_first_match(html, r"EMI\s*Starts?\s*from\\?\"[^\\]*INR\s*(\d[\d,]*)", flags=re.IGNORECASE))
    admission_deadline = _parse_iso_date(info.get("Admission Deadline"))
    start_date = _parse_iso_date(info.get("Start Date"))
    if not start_date:
        # JSON-LD courseSchedule.startDate as fallback
        if instances and isinstance(instances[0], dict):
            sched = instances[0].get("courseSchedule") or {}
            if isinstance(sched, dict):
                start_date = _parse_iso_date(sched.get("startDate"))
    programme_type = info.get("Type") or info.get("Programme Type")

    # Weekly hours
    body_text = soup.get_text(" ", strip=True)
    weekly_hours: float | None = None
    m_wh = re.search(r"(\d+)\s*to\s*(\d+)\s*hours?\s*a\s*week", body_text, re.IGNORECASE)
    if m_wh:
        weekly_hours = (int(m_wh.group(1)) + int(m_wh.group(2))) / 2.0
    else:
        m_wh1 = re.search(r"(\d+)\s*hours?\s*a\s*week", body_text, re.IGNORECASE)
        if m_wh1:
            weekly_hours = float(m_wh1.group(1))

    # Modules from embedded JSON
    modules = _extract_modules_from_embedded(html)

    # FAQs from JSON-LD
    faqs: list[dict[str, str | None]] = []
    main_entity = faq_ld.get("mainEntity") or []
    if isinstance(main_entity, list):
        for q in main_entity:
            if not isinstance(q, dict):
                continue
            question = (q.get("name") or "").strip()
            ans = q.get("acceptedAnswer") or {}
            ans_text = (ans.get("text") or "").strip() if isinstance(ans, dict) else ""
            # strip simple HTML tags from the answer
            ans_text = re.sub(r"<[^>]+>", " ", ans_text)
            ans_text = re.sub(r"\s+", " ", ans_text).strip()
            if question:
                faqs.append({"group": None, "question": question, "answer": ans_text or None})

    # Breadcrumb category (position 2 in JSON-LD: position 1 is "Home")
    breadcrumb_category: str | None = None
    items = bc_ld.get("itemListElement") or []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("position") == 2:
                breadcrumb_category = (item.get("name") or "").strip() or None
                break

    # Hero tagline: course description from JSON-LD, fallback to first <p> after title
    hero_tagline = (course_ld.get("description") or "").strip() or None
    if not hero_tagline:
        title_node = soup.find("h1") or soup.find("h2")
        if title_node is not None:
            hero_tagline = _text(title_node.find_next("p"))

    eligibility_raw, min_marks_pct, min_degree = _extract_eligibility(soup)

    return {
        "slug": slug,
        "url": url,
        "title": title,
        "provider": provider,
        "co_brand": co_brand,
        "programme_type": programme_type,
        "duration_weeks": duration_weeks,
        "duration_label": duration_label,
        "weekly_hours": weekly_hours,
        "start_date": start_date,
        "admission_deadline": admission_deadline,
        "emi_starts_from_inr": emi,
        "fee_inr_total": fee_inr_total,
        "fee_usd_total": fee_usd_total,
        "eligibility_raw": eligibility_raw,
        "min_marks_pct": min_marks_pct,
        "min_degree": min_degree,
        "modules": modules,
        "tools": _extract_tools(soup),
        "target_roles": _extract_target_roles(soup),
        "industries": _extract_industries(soup),
        "hiring_companies": _extract_hiring_companies(soup),
        "faculty": _extract_faculty(soup, html),
        "certificates": _extract_certificates(soup),
        "faqs": faqs,
        "breadcrumb_category": breadcrumb_category,
        "hero_tagline": hero_tagline,
        "key_highlights": _extract_key_highlights(soup),
        "testimonials": _extract_testimonials(soup),
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Parse a saved upGrad course HTML file into JSON.")
    ap.add_argument("html_path", help="Path to a saved HTML file (e.g. data/raw/<slug>.html)")
    ap.add_argument("--slug", default=None, help="Override slug; defaults to filename without extension")
    args = ap.parse_args()

    path = Path(args.html_path)
    slug = args.slug or path.stem
    parsed = parse(path.read_text(encoding="utf-8"), slug)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
