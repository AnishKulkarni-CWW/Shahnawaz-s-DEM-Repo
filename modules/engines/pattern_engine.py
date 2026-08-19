"""
FIDELITAS — Pattern & Typographic Detail Engine

Fills three specific gaps from the original spec that the general
similarity-based diff doesn't label explicitly enough on its own:

  - numbers / dates / prices: a single-digit change (¥12,800 -> ¥18,200)
    can score as "highly similar" under generic string similarity even
    though it's a critical business error, so these are extracted and
    compared on their own.
  - capitalization: flagged specifically (not just as a generic mismatch)
    when two strings are identical except for letter case.
  - full-width / half-width usage: a real, common Japanese emailer QA
    defect class (e.g. full-width Latin letters where half-width is
    expected, or half-width katakana where full-width is expected).
"""

import re

PRICE_RE = re.compile(r"[¥$￥]\s?[\d,]+(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?円")
DATE_RE = re.compile(r"\d{4}[/\-年]\d{1,2}[/\-月]\d{1,2}日?|\d{1,2}月\d{1,2}日|\d{1,2}[/\-]\d{1,2}")
NUMBER_RE = re.compile(r"(?<![\d.\w])\d{2,}(?:[.,]\d+)?(?![\d])")

FULLWIDTH_LATIN_RE = re.compile(r"[\uFF21-\uFF3A\uFF41-\uFF5A]")
FULLWIDTH_DIGIT_RE = re.compile(r"[\uFF10-\uFF19]")
HALFWIDTH_KATAKANA_RE = re.compile(r"[\uFF66-\uFF9D]")
HALFWIDTH_DIGIT_RE = re.compile(r"[0-9]")


def extract_prices(text: str) -> list:
    return PRICE_RE.findall(text or "")


def extract_dates(text: str) -> list:
    return DATE_RE.findall(text or "")


def extract_numbers(text: str) -> list:
    return NUMBER_RE.findall(text or "")


def compare_patterns(reference: str, actual: str) -> list:
    """Returns short human-readable descriptions of number/date/price
    mismatches between two matched strings."""
    findings = []
    for label, extractor in (("price", extract_prices), ("date", extract_dates), ("number", extract_numbers)):
        ref_vals = extractor(reference)
        act_vals = extractor(actual)
        missing = [v for v in ref_vals if v not in act_vals]
        extra = [v for v in act_vals if v not in ref_vals]
        if missing:
            findings.append(f'reference {label}(s) missing from actual: {", ".join(missing)}')
        if extra:
            findings.append(f'actual has {label}(s) not present in reference: {", ".join(extra)}')
    return findings


def capitalization_mismatch(reference: str, actual: str) -> str:
    """Returns a description if two strings match except for letter case,
    else None. Deliberately strict (whole-string case-insensitive match) to
    avoid false positives on otherwise-unrelated text."""
    if reference is None or actual is None or reference == actual:
        return None
    if reference.lower() != actual.lower():
        return None
    ref_tokens = re.findall(r"[A-Za-z]+", reference)
    act_tokens = re.findall(r"[A-Za-z]+", actual)
    for rt, at in zip(ref_tokens, act_tokens):
        if rt != at:
            return f'"{at}" should be "{rt}"'
    return "text matches the reference except for letter case"


def fullwidth_halfwidth_issues(text: str) -> list:
    issues = []
    if not text:
        return issues
    if FULLWIDTH_DIGIT_RE.search(text) and HALFWIDTH_DIGIT_RE.search(text):
        issues.append("mixes full-width and half-width numbers in the same text")
    if FULLWIDTH_LATIN_RE.search(text):
        issues.append("contains full-width Latin letters (Ａ-Ｚ style) — confirm half-width was not intended")
    if HALFWIDTH_KATAKANA_RE.search(text):
        issues.append("contains half-width katakana (ｶﾀｶﾅ style) — confirm full-width was not intended")
    return issues
