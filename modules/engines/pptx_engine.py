"""
FIDELITAS — PPTX Reference Engine

PPTX reference text has no positional ALT/CTA marker convention (unlike the
checklist workbook), so this engine checks *presence*: for every slide text
block, does a close match of that text appear anywhere in the HTML's ALT
attributes, link text, or visible body text? This is a genuinely weaker
guarantee than the checklist's positional match, and every issue this
engine raises says so explicitly rather than implying the same precision.

CTA button copy (pptx_cta_text) and CTA destination URLs (pptx_url) are
checked as two SEPARATE presence facts against the HTML's links, rather
than paired to each other — see pptx_parser.py's module docstring for why
a specific button<->URL pairing can't be honestly claimed from this deck's
shape structure.
"""

from ..models import Issue, Status, Severity, ReferenceVariant, ImplementationModel
from . import text_diff

PRESENCE_MATCH_THRESHOLD = 0.72
CTA_TEXT_MATCH_THRESHOLD = 0.6


def check_pptx_presence(variant: ReferenceVariant, impl: ImplementationModel) -> list:
    issues = []
    text_blocks = [b for b in variant.blocks if b.kind in ("pptx_body", "pptx_notes")]
    if not text_blocks:
        return issues

    haystacks = []
    for img in impl.images:
        if img.alt.strip():
            haystacks.append(text_diff.normalize_whitespace(img.alt))
    for link in impl.links:
        if link.text.strip():
            haystacks.append(text_diff.normalize_whitespace(link.text))
    body_norm = text_diff.normalize_whitespace(impl.text_content)

    for block in text_blocks:
        needle = text_diff.normalize_whitespace(block.text)
        if not needle:
            continue

        contained_in = None if needle in body_norm else next((h for h in haystacks if needle in h), None)
        if needle in body_norm or contained_in is not None:
            issues.append(Issue(
                category="PPTX Reference", title="Slide text found in implementation",
                status=Status.PASS, severity=Severity.INFO,
                expected=block.text, actual=contained_in,
                location=f"PPTX block #{block.order} ({block.kind.replace('pptx_', '')})",
                source_rule="PPTX presence check",
            ))
            continue

        idx, match, score = text_diff.best_match(needle, haystacks)
        if idx is not None and score >= PRESENCE_MATCH_THRESHOLD:
            issues.append(Issue(
                category="PPTX Reference", title="Slide text closely matches an element in the implementation",
                status=Status.PASS if score >= 0.97 else Status.WARNING,
                severity=Severity.INFO if score >= 0.97 else Severity.LOW,
                expected=block.text, actual=match,
                difference=None if score >= 0.97 else text_diff.describe_diff(block.text, match),
                location=f"PPTX block #{block.order} ({block.kind.replace('pptx_', '')})",
                recommendation=None if score >= 0.97 else "Close but not exact — confirm this is the intended match, not a coincidence.",
                source_rule="PPTX presence check",
            ))
        else:
            issues.append(Issue(
                category="PPTX Reference", title="Slide text not found anywhere in the implementation",
                status=Status.MANUAL_REVIEW, severity=Severity.MEDIUM,
                expected=block.text,
                location=f"PPTX block #{block.order} ({block.kind.replace('pptx_', '')})",
                recommendation="This is a presence check across the whole page, not a positional match — please confirm manually before treating this as a genuine content gap. It may be intentionally reworded, or the PPTX slide may be reference/context only.",
                source_rule="PPTX presence check",
            ))

    return issues


def check_pptx_cta_elements(variant: ReferenceVariant, impl: ImplementationModel) -> list:
    """Checks CTA button copy and CTA destination URLs from the PPTX as two
    independently-verifiable presence facts against the HTML's real links —
    see the module docstring for why they aren't paired to each other."""
    issues = []
    cta_text_blocks = [b for b in variant.blocks if b.kind == "pptx_cta_text"]
    url_blocks = [b for b in variant.blocks if b.kind == "pptx_url"]

    link_texts = [text_diff.normalize_whitespace(l.text) for l in impl.links if l.text.strip()]
    link_hrefs = [l.href for l in impl.links if l.href]

    for block in cta_text_blocks:
        needle = text_diff.normalize_whitespace(block.text)
        idx, match, score = text_diff.best_match(needle, link_texts)
        if idx is not None and score >= CTA_TEXT_MATCH_THRESHOLD:
            issues.append(Issue(
                category="PPTX Reference", title="CTA button copy from PPTX found among HTML links",
                status=Status.PASS if score >= 0.97 else Status.WARNING,
                severity=Severity.INFO if score >= 0.97 else Severity.LOW,
                expected=block.text, actual=match,
                difference=None if score >= 0.97 else text_diff.describe_diff(block.text, match),
                location=f"PPTX block #{block.order} (CTA button mockup)",
                source_rule="PPTX CTA copy presence check",
            ))
        else:
            issues.append(Issue(
                category="PPTX Reference", title="CTA button copy from PPTX not found among HTML links",
                status=Status.MANUAL_REVIEW, severity=Severity.MEDIUM,
                expected=block.text,
                location=f"PPTX block #{block.order} (CTA button mockup)",
                recommendation="No HTML link text closely matches this button label from the design mockup — confirm this CTA was implemented.",
                source_rule="PPTX CTA copy presence check",
            ))

    for block in url_blocks:
        target_base = (block.url or "").split("?")[0].rstrip("/")
        found = any((h.split("?")[0].rstrip("/") == target_base) for h in link_hrefs if h)
        if found:
            issues.append(Issue(
                category="PPTX Reference", title="CTA destination URL from PPTX found in HTML links",
                status=Status.PASS, severity=Severity.INFO,
                expected=block.url, location=f"PPTX block #{block.order} (CTA URL)",
                source_rule="PPTX CTA URL presence check",
            ))
        else:
            issues.append(Issue(
                category="PPTX Reference", title="CTA destination URL from PPTX not found in HTML links",
                status=Status.MANUAL_REVIEW, severity=Severity.MEDIUM,
                expected=block.url, location=f"PPTX block #{block.order} (CTA URL)",
                recommendation="No HTML link points to this destination (ignoring tracking parameters) — confirm this CTA target was implemented, or that the tracking parameters weren't changed enough to break the match.",
                source_rule="PPTX CTA URL presence check",
            ))

    return issues


def check_pptx_reference_metadata(variant: ReferenceVariant) -> list:
    """Surfaces reference metadata the PPTX itself states (e.g. an S3 link
    written directly in the brief slide) as informational context — not
    compared against anything, just shown so the QA engineer can cross-check
    it against the actual URL(s) they're auditing."""
    issues = []
    for block in variant.blocks:
        if block.kind == "pptx_reference_url":
            issues.append(Issue(
                category="PPTX Reference", title=f"Reference URL stated in PPTX: {block.text}",
                status=Status.INFO, severity=Severity.INFO,
                expected=block.url, location=f"PPTX block #{block.order}",
                recommendation="Confirm this matches the S3/Live URL you're actually auditing against.",
                source_rule="PPTX reference metadata",
            ))
    return issues
