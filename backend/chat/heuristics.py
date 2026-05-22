"""Programme-type heuristic fallbacks (Phase 11.3).

When a specific field is null for a course, the bot still answers using a
known-good approximation for that programme type, clearly framed with a
"typically" caveat and a pointer to the official page.

Source: upGrad's published programme-type conventions (BUILD_PLAN.md Appendix A)
plus a manual audit of the catalog.
"""

from __future__ import annotations

ELIGIBILITY_HEURISTICS = {
    "bootcamp": "no strict degree required, typically open to anyone with 12th-pass or equivalent and an interest in the field",
    "certificate": "open to graduates of any discipline; some certs also accept current undergrads",
    "pgp": "bachelor's degree in any discipline, often with a minimum 50% aggregate",
    "executive_cert": "bachelor's degree plus some work experience, typically 1+ years",
    "masters": "bachelor's degree in a related or quantitative discipline, with a minimum aggregate (varies by partner)",
    "mba": "bachelor's degree, often with 2+ years of work experience; entrance test may apply",
    "dba": "master's or MBA plus 5+ years of senior work experience",
    "phd_alternative": "master's degree in a related discipline plus a written proposal",
}

DURATION_HEURISTICS = {
    "bootcamp": "3 to 6 months full-time intensive",
    "certificate": "2 to 6 months part-time",
    "pgp": "6 to 12 months part-time",
    "executive_cert": "6 to 9 months part-time",
    "masters": "12 to 24 months part-time",
    "mba": "12 to 24 months part-time",
    "dba": "36 to 48 months part-time",
    "phd_alternative": "36 to 48 months part-time",
}

FORMAT_HEURISTICS = {
    "bootcamp": "fully online with live cohort sessions, usually 8-12 hours per week",
    "certificate": "online and largely self-paced with some live sessions",
    "pgp": "online cohort with weekend live classes",
    "executive_cert": "online cohort, weekend live classes",
    "masters": "online with optional campus immersion",
    "mba": "online with required campus immersion modules",
    "dba": "online with periodic on-campus residencies",
    "phd_alternative": "online with periodic on-campus residencies",
}

FEE_HEURISTICS = {
    "bootcamp": "under 1 lakh INR upfront, EMI plans usually available",
    "certificate": "under 1.5 lakh INR upfront",
    "pgp": "around 3 to 5 lakh INR, EMI plans available",
    "executive_cert": "around 2 to 4 lakh INR",
    "masters": "5 to 8 lakh INR over the programme duration",
    "mba": "6 to 10 lakh INR over the programme duration",
    "dba": "10 lakh INR and above",
    "phd_alternative": "10 lakh INR and above",
}

# Map a <heuristic:field> placeholder to its table.
HEURISTIC_TABLES = {
    "eligibility": ELIGIBILITY_HEURISTICS,
    "duration": DURATION_HEURISTICS,
    "format": FORMAT_HEURISTICS,
    "fees": FEE_HEURISTICS,
}

PROGRAMME_TYPE_KEYS = (
    "bootcamp", "certificate", "pgp", "executive_cert",
    "masters", "mba", "dba", "phd_alternative",
)


def normalize_programme_type(s: str | None) -> str:
    """Map free-text programme_type (e.g. 'Executive Certificate') to a canonical key.

    Order matters: more specific signals (dba/phd/mba/executive) are checked before
    the broad 'master'/'certificate' catch-alls. Defaults to 'certificate'.
    """
    t = (s or "").lower().strip()
    if not t:
        return "certificate"
    if "bootcamp" in t or "job-ready" in t or "job ready" in t:
        return "bootcamp"
    if "mba" in t or "master of business" in t:
        return "mba"
    # DBA (incl. "Doctorate/Doctor of Business Administration") must beat the generic phd check.
    if "dba" in t or ("business administration" in t and ("doctor" in t or "doctorate" in t)) \
            or "doctor of business" in t or "doctorate of business" in t:
        return "dba"
    if "phd" in t or "ph.d" in t or "doctoral" in t or "doctorate" in t:
        return "phd_alternative"
    if "executive" in t:
        return "executive_cert"
    if any(k in t for k in ("master", "msc", "m.sc", "ms ", "pg diploma", "post graduate diploma", "pgd")):
        return "masters"
    if "pgp" in t or "post graduate program" in t or "postgraduate program" in t or "pg program" in t:
        return "pgp"
    if "certificate" in t or "certification" in t or "cert" in t:
        return "certificate"
    return "certificate"


def heuristic_for(field: str, programme_type_key: str | None) -> str | None:
    """Return the heuristic string for a `<heuristic:field>` placeholder, or None."""
    table = HEURISTIC_TABLES.get(field)
    if table is None:
        return None
    key = programme_type_key if programme_type_key in PROGRAMME_TYPE_KEYS else "certificate"
    return table.get(key)


def heuristic_block(programme_type_key: str | None) -> str:
    """The fallback-heuristics section appended to the course-QA system prompt."""
    key = programme_type_key if programme_type_key in PROGRAMME_TYPE_KEYS else "certificate"
    return (
        f"Fallback heuristics for THIS programme_type ({key}) "
        "(use ONLY if the specific data above is null):\n"
        f"- Eligibility: {ELIGIBILITY_HEURISTICS[key]}\n"
        f"- Duration: {DURATION_HEURISTICS[key]}\n"
        f"- Format: {FORMAT_HEURISTICS[key]}\n"
        f"- Fees: {FEE_HEURISTICS[key]}\n\n"
        "If a heuristic is used to answer, you must include one of: "
        '"typically", "usually", "in most cases", "as a rule". '
        'Always end such answers by pointing to "this course\'s page" for the exact terms '
        "(never call it 'the official upGrad page' — you are upGrad)."
    )
