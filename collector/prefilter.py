"""Deterministic rule pre-filter. No model call, standard library only."""

from __future__ import annotations

import re

CLOUD_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
CARD_CANDIDATE_RE = re.compile(r"(?<![A-Za-z0-9])(?:\d[ -]?){13,19}(?![A-Za-z0-9])")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
PASSWORD_LINE_RE = re.compile(r"(?i)\|\s*password\s*\||password\s*[:=]\s*\S{4,}")

KNOWN_SPACES = {
    "Customer Care", "People", "Operations", "Platform", "Product",
    "Finance", "Security", "Fleet Operations",
}

# Space to domain, decided with no model: the People space is personal data, always
# restricted on ingest, refined (never loosened) once the classifier runs in P2.
RESTRICTED_SPACES = {"People"}


def is_restricted(space: str | None) -> bool:
    return space in RESTRICTED_SPACES


def _luhn_valid(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact(text: str, span: tuple[int, int]) -> str:
    start, end = span
    lo = max(0, start - 12)
    hi = min(len(text), end + 12)
    return text[lo:start] + "[redacted]" + text[end:hi]


def find_hits(text: str, *, space: str | None = None) -> list[dict]:
    """Returns one entry per rule hit: {rule, span, snippet}. Never the raw secret alone."""
    hits: list[dict] = []
    for match in CLOUD_KEY_RE.finditer(text):
        hits.append({"rule": "cloud-key", "span": match.span(), "snippet": _redact(text, match.span())})
    for match in CARD_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"[ -]", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            hits.append({"rule": "card-luhn", "span": match.span(), "snippet": _redact(text, match.span())})
    for match in IBAN_RE.finditer(text):
        hits.append({"rule": "iban", "span": match.span(), "snippet": _redact(text, match.span())})
    for match in PRIVATE_KEY_RE.finditer(text):
        hits.append({"rule": "private-key", "span": match.span(), "snippet": _redact(text, match.span())})
    for match in PASSWORD_LINE_RE.finditer(text):
        hits.append({"rule": "password-line", "span": match.span(), "snippet": _redact(text, match.span())})
    if space is not None and space not in KNOWN_SPACES:
        hits.append({"rule": "unknown-space", "span": (0, 0), "snippet": space})
    return hits
