"""
FIDELITAS — Japanese-aware text comparison utilities.

Deterministic, no AI involved. Detects the specific classes of mismatch
called out in the checklist: punctuation swaps (。vs！), missing brackets
（「」）, double/leading/trailing spacing, and general character-level
differences — reported as a short human-readable diff, not a wall of text.
"""

import difflib
import re

FULLWIDTH_TO_HALFWIDTH_PUNCT = {
    "。": [". ", "."],
    "、": [", ", ","],
    "「": ["\""],
    "」": ["\""],
    "！": ["!"],
    "？": ["?"],
    "：": [":"],
}

BRACKET_PAIRS = [("「", "」"), ("『", "』"), ("（", "）"), ("(", ")")]


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def spacing_issues(text: str) -> list:
    """Returns list of short descriptions of spacing problems in `text`."""
    issues = []
    if text is None:
        return issues
    if re.search(r"  +", text):
        issues.append("double/multiple spaces detected")
    if re.search(r"　　+", text):
        issues.append("double full-width (Japanese) spaces detected")
    if text != text.strip() and text.strip() != "":
        issues.append("leading or trailing whitespace")
    if re.search(r"\n\s*\n\s*\n", text):
        issues.append("multiple consecutive line breaks")
    return issues


def bracket_balance_issues(text: str) -> list:
    issues = []
    if not text:
        return issues
    for open_b, close_b in BRACKET_PAIRS:
        if text.count(open_b) != text.count(close_b):
            issues.append(f"unbalanced {open_b}{close_b} brackets")
    return issues


def describe_diff(reference: str, actual: str) -> str:
    """Short human-readable explanation of the first meaningful difference
    between two strings, in the same style as the spec examples:
    'Difference: "!" was used instead of "。"'
    """
    if reference == actual:
        return "No difference"
    ref, act = reference or "", actual or ""

    sm = difflib.SequenceMatcher(None, ref, act)
    opcodes = [op for op in sm.get_opcodes() if op[0] != "equal"]
    if not opcodes:
        return "No difference"

    tag, i1, i2, j1, j2 = opcodes[0]
    ref_chunk = ref[i1:i2]
    act_chunk = act[j1:j2]

    if tag == "replace":
        return f'"{act_chunk}" was used instead of "{ref_chunk}"'
    if tag == "delete":
        return f'"{ref_chunk}" is missing from the actual text'
    if tag == "insert":
        return f'extra text "{act_chunk}" found that is not in the reference'
    return f"text differs starting around: reference=\"{ref_chunk}\" actual=\"{act_chunk}\""


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a or "", b or "").ratio()


def best_match(target: str, candidates: list) -> tuple:
    """Finds the candidate string most similar to target.
    Returns (index, candidate, score) or (None, None, 0.0) if candidates is empty."""
    if not candidates:
        return None, None, 0.0
    best_i, best_s, best_score = None, None, -1.0
    for i, c in enumerate(candidates):
        score = similarity(normalize_whitespace(target), normalize_whitespace(c))
        if score > best_score:
            best_i, best_s, best_score = i, c, score
    return best_i, best_s, best_score
