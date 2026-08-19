"""
FIDELITAS — CTA Engine

Compares reference CTA (text + URL) blocks from the checklist against the
actual <a> links found in the developer HTML, and checks CTA-specific
technical rules pulled from the dev checklist (Adebis tracking param
present, link goes to the CTA only rather than wrapping a whole banner —
best-effort heuristic).
"""

from ..models import Issue, Status, Severity, ReferenceVariant, ImplementationModel
from . import text_diff, pattern_engine

TEXT_MATCH_THRESHOLD = 0.6


def check_ctas(variant: ReferenceVariant, impl: ImplementationModel) -> list:
    issues = []
    cta_blocks = [b for b in variant.blocks if b.kind == "cta"]
    if not cta_blocks:
        return issues

    html_texts = [l.text for l in impl.links]
    used = set()

    for block in cta_blocks:
        candidates = [t if i not in used else "\uffff" for i, t in enumerate(html_texts)]
        idx, match_text, score = text_diff.best_match(block.text, candidates)

        if idx is None or score < TEXT_MATCH_THRESHOLD:
            issues.append(Issue(
                category="CTA", title="Reference CTA not found in HTML",
                status=Status.FAIL, severity=Severity.CRITICAL,
                expected=f'"{block.text}" -> {block.url}',
                actual="(no matching CTA link found)",
                recommendation="This CTA button appears to be missing from the implementation entirely.",
                source_rule="Is each CTA set correctly?",
            ))
            continue

        used.add(idx)
        link = impl.links[idx]

        if match_text.strip() == block.text.strip():
            issues.append(Issue(
                category="CTA", title="CTA text matches reference",
                status=Status.PASS, severity=Severity.INFO,
                expected=block.text, actual=match_text,
                location=f"HTML CTA #{idx+1}",
                source_rule="Is each CTA set correctly?",
            ))
        else:
            issues.append(Issue(
                category="CTA", title="CTA text differs from reference",
                status=Status.FAIL, severity=Severity.HIGH,
                expected=block.text, actual=match_text,
                difference=text_diff.describe_diff(block.text, match_text),
                location=f"HTML CTA #{idx+1}",
                recommendation="Update the CTA button copy to match the client-approved reference text exactly.",
                source_rule="Is each CTA set correctly?",
            ))

        # URL check — compare ignoring tracking-parameter noise for the base match,
        # but flag if the base destination path differs.
        ref_base = _strip_query(block.url)
        actual_base = _strip_query(link.href)
        if ref_base == actual_base:
            issues.append(Issue(
                category="CTA", title="CTA destination URL matches reference",
                status=Status.PASS, severity=Severity.INFO,
                expected=block.url, actual=link.href,
                location=f"HTML CTA #{idx+1}",
                source_rule="Is each CTA set correctly?",
            ))
        else:
            issues.append(Issue(
                category="CTA", title="CTA destination URL differs from reference",
                status=Status.FAIL, severity=Severity.CRITICAL,
                expected=block.url, actual=link.href,
                location=f"HTML CTA #{idx+1}",
                recommendation="This CTA points to a different URL than the client-approved reference.",
                source_rule="Is each CTA set correctly?",
            ))

        cap_issue = pattern_engine.capitalization_mismatch(block.text, match_text)
        if cap_issue:
            issues.append(Issue(
                category="CTA", title="CTA capitalization differs from reference",
                status=Status.FAIL, severity=Severity.MEDIUM,
                expected=block.text, actual=match_text, difference=cap_issue,
                location=f"HTML CTA #{idx+1}",
                source_rule="Is each CTA set correctly?",
            ))

        if not link.href or link.href.strip() in ("#", ""):
            issues.append(Issue(
                category="CTA", title="CTA link has an empty or placeholder href",
                status=Status.FAIL, severity=Severity.CRITICAL,
                actual=link.href or "(empty)", location=f"HTML CTA #{idx+1}",
                recommendation="This CTA will not navigate anywhere — set a real destination URL.",
                source_rule="Is each CTA set correctly?",
            ))

        if not _has_tracking_param(link.href):
            issues.append(Issue(
                category="CTA", title="CTA link has no visible tracking parameter",
                status=Status.WARNING, severity=Severity.MEDIUM,
                actual=link.href, location=f"HTML CTA #{idx+1}",
                recommendation="Confirm the ADEBIS tracking parameter has been applied to this CTA link before delivery.",
                source_rule="Is ADEBis set correctly?",
            ))

    unmatched = [i for i in range(len(html_texts)) if i not in used and html_texts[i]]
    if unmatched:
        issues.append(Issue(
            category="CTA", title=f"{len(unmatched)} link(s) in HTML have no corresponding reference CTA",
            status=Status.INFO, severity=Severity.LOW,
            location=f"HTML link(s) #{[i+1 for i in unmatched]}",
            recommendation="Confirm these are intentional (e.g. footer/unsubscribe/legal links not itemized as CTAs in the checklist).",
        ))

    return issues


def _strip_query(url: str) -> str:
    if not url:
        return ""
    return url.split("?")[0].rstrip("/")


def _has_tracking_param(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return any(p in lowered for p in ["adebis", "utm_", "trk", "cid=", "mkt_tok"])
