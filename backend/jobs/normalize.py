"""Canonical forms used for de-duplication, tags, seniority and salary filters.

The scrapers parse each board's formats; this module makes the results
comparable *across* boards. "Sr. Data Engineer (m/f/d)" at "Acme GmbH" and
"Senior Data Engineer" at "Acme" must end up with the same fingerprint.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from django.conf import settings

LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "plc", "gmbh", "ag", "bv", "nv", "sa", "sas", "sarl",
    "srl", "spa", "lda", "oy", "ab", "as", "aps", "kg", "co", "corp", "corporation", "company", "pty", "se",
}

# Gender/inclusion markers that German and Austrian boards add to titles.
GENDER_MARKERS = re.compile(r"\((?:[mwfdx]\s*/\s*){1,3}[mwfdx]\)|\((?:all genders?|alle)\)|\b[mwfd]/[mwfd]/[mwfdx]\b", re.I)

TITLE_ABBREVIATIONS = {
    "sr": "senior",
    "snr": "senior",
    "jr": "junior",
    "jnr": "junior",
    "eng": "engineer",
    "engr": "engineer",
    "dev": "developer",
    "mgr": "manager",
    "fullstack": "full stack",
    "frontend": "front end",
    "backend": "back end",
    "ml": "machine learning",
    "sre": "site reliability engineer",
}


def _ascii_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ").replace("+", " plus ").replace("#", " sharp ")
    return re.findall(r"[a-z0-9]+", text)


def company_key(name: str) -> str:
    """'Northwind Analytics GmbH' and 'northwind analytics' -> 'northwind analytics'."""
    words = _ascii_words(name or "")
    # "B.V." becomes ["b", "v"]; glue single letters back so the suffix is recognised.
    glued: list[str] = []
    for word in words:
        if len(word) == 1 and glued and len(glued[-1]) <= 2 and glued[-1].isalpha() and glued[-1] not in {"and"}:
            glued[-1] += word
        else:
            glued.append(word)
    while len(glued) > 1 and glued[-1] in LEGAL_SUFFIXES:
        glued.pop()
    return " ".join(glued)


def title_key(title: str) -> str:
    """'Sr. Full-Stack Developer (m/f/d)' -> 'senior full stack developer'."""
    title = GENDER_MARKERS.sub(" ", title or "")
    words: list[str] = []
    for word in _ascii_words(title):
        words.extend(TITLE_ABBREVIATIONS.get(word, word).split())
    return " ".join(words)


def place_key(workplace: str | None, city: str | None, country: str | None) -> str:
    if workplace == "remote":
        return "remote"
    if city:
        return " ".join(_ascii_words(city))
    return (country or "").lower() or "unknown"


def fingerprint(company: str, title: str, workplace: str | None, city: str | None, country: str | None) -> str:
    raw = "|".join([company_key(company), title_key(title), place_key(workplace, city, country)])
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


SENIORITY_PATTERNS = [
    ("intern", re.compile(r"\b(intern|internship|trainee|working student|werkstudent)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|graduate|entry[- ]level)\b", re.I)),
    ("principal", re.compile(r"\b(principal|distinguished)\b", re.I)),
    ("staff", re.compile(r"\bstaff\b", re.I)),
    ("lead", re.compile(r"\b(lead|head of|tech lead)\b", re.I)),
    ("manager", re.compile(r"\b(manager|director|vp)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?|snr)\b", re.I)),
]


def seniority(title: str, employment_type: str | None = None) -> str:
    if employment_type == "internship":
        return "intern"
    for level, pattern in SENIORITY_PATTERNS:
        if pattern.search(title or ""):
            return level
    return "mid"


PERIOD_FACTORS = {"year": 1, "month": 12, "week": 52, "day": 260, "hour": 2080}


def annual_usd(amount: int | float | None, currency: str | None, period: str | None) -> int | None:
    """Rough yearly USD figure for filtering and sorting. None when we can't say."""
    if amount is None or not currency or period not in PERIOD_FACTORS:
        return None
    rate = settings.FX_TO_USD.get(currency.upper())
    if rate is None:
        return None
    return int(round(float(amount) * PERIOD_FACTORS[period] * rate, -2))

def compute_metrics(data=None):
    if data is None:
        return None
    return data