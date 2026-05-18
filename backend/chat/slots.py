"""Slot definitions + alternative phrasings + quick-reply chips.

Deviates from docs/PROMPTS.md §2 in two ways the user explicitly asked for:
1. Only four slots are HARD (years_experience, can_code, weekly_hours, domain_interest)
   so the bot reaches RECOMMEND in roughly four turns, not seven.
2. Phrasings carry no em dashes, per the user's tone request.
"""

from __future__ import annotations

SLOTS = [
    # name,                 type,    hard,  topic_group
    ("current_role",        "str",   False, "background"),
    ("years_experience",    "int",   True,  "background"),
    ("can_code",            "bool",  True,  "background"),
    ("education_level",     "enum",  False, "background"),
    ("min_marks_pct_est",   "int",   False, "background"),
    ("career_goal",         "enum",  False, "goals"),
    ("domain_interest",     "tags",  True,  "goals"),
    ("weekly_hours",        "int",   True,  "logistics"),
    ("format_preference",   "enum",  False, "logistics"),
    ("schedule_preference", "enum",  False, "logistics"),
    ("budget_bucket",       "enum",  False, "logistics"),
    ("prestige_preference", "enum",  False, "vibe"),
    ("vibe_preference",     "tags",  False, "vibe"),
]

SLOT_PHRASINGS = {
    "current_role": [
        "what do you do for a living?",
        "what's your day job look like?",
        "what's on your business card right now?",
    ],
    "years_experience": [
        "how many years have you been working?",
        "out of curiosity, how many years into your career are you?",
        "rough number, years working?",
    ],
    "education_level": [
        "what's the highest you've studied?",
        "remind me, bachelor's, master's, somewhere in between?",
        "where did formal education stop for you?",
    ],
    "min_marks_pct_est": [
        "ballpark, did college go well grades-wise?",
        "rough percentage you finished college with?",
        "did the grades work out, or was it a 'just passed' situation?",
    ],
    "can_code": [
        "how cozy are you with code?",
        "if I dropped a Python file in front of you, yes or no?",
        "any programming in your day-to-day?",
    ],
    "career_goal": [
        "what's the next move, switch fields, climb, or something else?",
        "if this works out, what does 'after' look like?",
        "aiming at a promotion, a switch, or sharpening the same role?",
    ],
    "domain_interest": [
        "any specific area pulling you, AI, product, data, MBA, design?",
        "what's the topic you keep clicking on lately?",
        "if you had to pick one corner to live in for two years, which?",
    ],
    "weekly_hours": [
        "realistically, how many hours a week could you give this?",
        "be honest, weekly time you can actually carve out?",
        "between work and life, what does 'study time' look like?",
    ],
    "format_preference": [
        "online, in-person, or you'd be happy with a mix?",
        "classroom person, or laptop-at-home person?",
        "any preference between fully online and hybrid?",
    ],
    "schedule_preference": [
        "fixed cohort or self-paced, what fits?",
        "weekend live sessions, weekday evenings, or self-paced?",
        "do you like cohort discipline, or self-paced freedom?",
    ],
    "budget_bucket": [
        "how are you thinking about cost, any rough ceiling?",
        "is this a 'company pays' situation or out of pocket?",
        "ballpark budget, under 1L, 1 to 3L, 3 to 5L, more?",
    ],
    "prestige_preference": [
        "does it matter to you whose name is on the certificate?",
        "brand-wise, are you reaching for an IIT/IIM tag, or industry-led is fine?",
        "is the institution name important, or is it about the skills?",
    ],
    "vibe_preference": [
        "what vibe, rigorous and academic, or applied and hands-on?",
        "more 'build stuff with mentors', or 'sit with research papers'?",
        "do you like cohort energy, or quiet self-paced grinding?",
    ],
}


SLOT_QUICK_REPLIES: dict[str, list[str]] = {
    # current_role: free text, no chips
    "years_experience": ["0", "1-2", "3-5", "6-10", "10+"],
    "education_level": ["Diploma", "Bachelor's", "Master's", "PhD"],
    "min_marks_pct_est": ["<60%", "60-70%", "70-80%", "80%+"],
    "can_code": ["Yes", "A little", "Not really"],
    "career_goal": ["Switch fields", "Promotion", "Skill up", "Start a venture", "Academic"],
    "domain_interest": ["AI / ML", "Data Science", "Product Mgmt", "Generative AI", "MBA / DBA", "Software Engg", "Cloud", "Marketing"],
    "weekly_hours": ["5", "8-10", "12-15", "20+"],
    "format_preference": ["Online", "Hybrid", "In-person"],
    "schedule_preference": ["Self-paced", "Weekend cohort", "Weekday cohort"],
    "budget_bucket": ["<1L", "1-3L", "3-5L", "5-10L", "10L+"],
    "prestige_preference": ["IIT / IIM", "Global uni", "Industry-led", "Doesn't matter"],
    "vibe_preference": ["Rigorous", "Hands-on", "Research-heavy", "Industry-led"],
}


STARTER_CATEGORY_CHIPS = [
    "AI / ML",
    "Data Science",
    "Product Mgmt",
    "Generative AI",
    "MBA / DBA",
    "Software Engg",
]


SLOT_BY_NAME = {name: (name, typ, hard, group) for (name, typ, hard, group) in SLOTS}
HARD_SLOTS = [name for (name, _, hard, _) in SLOTS if hard]
SOFT_SLOTS = [name for (name, _, hard, _) in SLOTS if not hard]


def slot_topic_group(slot_name: str) -> str | None:
    entry = SLOT_BY_NAME.get(slot_name)
    return entry[3] if entry else None


def is_hard(slot_name: str) -> bool:
    entry = SLOT_BY_NAME.get(slot_name)
    return bool(entry and entry[2])
