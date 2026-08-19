"""
FIDELITAS — Content Engine

Compares the reference content blocks extracted from the client checklist
(mail title + sequential ALT texts) against the actual images found in the
developer HTML. Uses similarity matching rather than strict positional
matching, because a handful of extra/missing images shouldn't cascade into
false mismatches for everything downstream.
"""

from ..models import Issue, Status, Severity, ReferenceVariant, ImplementationModel
from . import text_diff, pattern_engine

SIMILARITY_MATCH_THRESHOLD = 0.55  # below this we call it "missing", not "mismatched"


def check_mail_title(variant: ReferenceVariant, impl: ImplementationModel) -> list:
    issues = []
    title_block = next((b for b in variant.blocks if b.kind == "title"), None)
    if not title_block:
        return issues

    # The mail "title" in these checklists is the subject line, which is not
    # literally rendered in a <title> tag for HTML emailers — it's set at
    # send-time. We can only compare it against <title> if present, and
    # otherwise mark it for manual/ESP-level verification.
    if impl.title:
        diff_text = text_diff.describe_diff(title_block.text, impl.title)
        if impl.title.strip() == title_block.text.strip():
            issues.append(Issue(
                category="Content", title="Mail title matches reference",
                status=Status.PASS, severity=Severity.INFO,
                expected=title_block.text, actual=impl.title,
                source_rule="Is the subject set correctly?",
            ))
        else:
            issues.append(Issue(
                category="Content", title="Mail title differs from reference",
                status=Status.FAIL, severity=Severity.HIGH,
                expected=title_block.text, actual=impl.title, difference=diff_text,
                recommendation="Confirm the actual send subject line with the ESP/distribution platform — the HTML <title> tag is not always the delivered subject.",
                source_rule="Is the subject set correctly?",
            ))
    else:
        issues.append(Issue(
            category="Content", title="Subject line cannot be verified from HTML alone",
            status=Status.MANUAL_REVIEW, severity=Severity.MEDIUM,
            expected=title_block.text,
            recommendation="Subject lines are set at the ESP/distribution level, not always present in the HTML. Verify manually against the reference in the send platform (e.g. ADEBIS / distribution tool).",
            source_rule="Is the subject set correctly?",
        ))
    return issues


def check_alt_texts(variant: ReferenceVariant, impl: ImplementationModel) -> list:
    issues = []
    alt_blocks = [b for b in variant.blocks if b.kind == "alt"]
    if not alt_blocks:
        return issues

    html_alts = [img.alt for img in impl.images]
    used = set()

    for block in alt_blocks:
        candidates = [a if i not in used else "\uffff" for i, a in enumerate(html_alts)]
        idx, match, score = text_diff.best_match(block.text, candidates)

        if idx is None or score < SIMILARITY_MATCH_THRESHOLD:
            issues.append(Issue(
                category="ALT Text", title="Reference ALT text not found in HTML",
                status=Status.FAIL, severity=Severity.CRITICAL,
                expected=block.text, actual="(no matching image found)",
                location=f"Reference block #{block.order}",
                recommendation="Add or restore this image with the correct ALT attribute — no image in the HTML has similar ALT text.",
                source_rule="Is ALT set correctly?",
            ))
            continue

        used.add(idx)
        if score >= 0.999:
            issues.append(Issue(
                category="ALT Text", title="ALT text matches reference",
                status=Status.PASS, severity=Severity.INFO,
                expected=block.text, actual=match,
                location=f"Reference block #{block.order} / HTML image #{idx+1}",
                source_rule="Is ALT set correctly?",
            ))
        else:
            diff_text = text_diff.describe_diff(block.text, match)
            issues.append(Issue(
                category="ALT Text", title="ALT text differs from reference",
                status=Status.FAIL, severity=Severity.HIGH,
                expected=block.text, actual=match, difference=diff_text,
                location=f"Reference block #{block.order} / HTML image #{idx+1}",
                recommendation="Update the ALT attribute to match the client-approved reference text exactly.",
                source_rule="Is ALT set correctly?",
            ))

        sp_issues = text_diff.spacing_issues(match)
        for sp in sp_issues:
            issues.append(Issue(
                category="Spacing", title=f"ALT text spacing issue: {sp}",
                status=Status.WARNING, severity=Severity.LOW,
                actual=match, location=f"HTML image #{idx+1}",
                recommendation="Remove the extra/unnecessary whitespace from the ALT attribute.",
                source_rule="Are there any unnecessary line breaks or spaces?",
            ))

        br_issues = text_diff.bracket_balance_issues(match)
        for b in br_issues:
            issues.append(Issue(
                category="Content", title=f"ALT text bracket issue: {b}",
                status=Status.WARNING, severity=Severity.MEDIUM,
                actual=match, location=f"HTML image #{idx+1}",
                recommendation="Check for a missing opening/closing Japanese bracket 「」 in the ALT text.",
                source_rule="Is ALT set correctly?",
            ))

        cap_issue = pattern_engine.capitalization_mismatch(block.text, match)
        if cap_issue:
            issues.append(Issue(
                category="Content", title="Capitalization differs from reference",
                status=Status.FAIL, severity=Severity.MEDIUM,
                expected=block.text, actual=match, difference=cap_issue,
                location=f"HTML image #{idx+1}",
                recommendation="Match the exact letter case used in the reference (brand/product/model names are usually case-sensitive).",
                source_rule="Is ALT set correctly?",
            ))

        pattern_findings = pattern_engine.compare_patterns(block.text, match)
        for pf in pattern_findings:
            issues.append(Issue(
                category="Content", title=f"Number/date/price mismatch: {pf}",
                status=Status.FAIL, severity=Severity.HIGH,
                expected=block.text, actual=match,
                location=f"HTML image #{idx+1}",
                recommendation="Double-check this figure against the reference — numeric/price/date errors are high-impact.",
                source_rule="Is ALT set correctly?",
            ))

        width_issues = pattern_engine.fullwidth_halfwidth_issues(match)
        for wi in width_issues:
            issues.append(Issue(
                category="Content", title=f"Full-width/half-width character issue: {wi}",
                status=Status.WARNING, severity=Severity.LOW,
                actual=match, location=f"HTML image #{idx+1}",
                recommendation="Confirm the intended width convention with the reference text.",
                source_rule="Is ALT set correctly?",
            ))

    unmatched_html = [i for i in range(len(html_alts)) if i not in used and html_alts[i]]
    if unmatched_html:
        issues.append(Issue(
            category="ALT Text", title=f"{len(unmatched_html)} image(s) in HTML have no corresponding reference block",
            status=Status.INFO, severity=Severity.LOW,
            location=f"HTML image(s) #{[i+1 for i in unmatched_html]}",
            recommendation="Confirm these images are intentional (e.g. spacer/decorative images not itemized in the checklist).",
        ))

    return issues


def check_dynamic_block_references(variant: ReferenceVariant) -> list:
    """▼BlockText references (e.g. "%%block1%%") are template/merge-tag
    placeholders, not literal content — the checklist itself doesn't know
    what they resolve to. Comparing them against static HTML would produce
    a guaranteed false failure on every single run, so they are never fed
    into the text-matching engines above. Instead they're surfaced here as
    an explicit, honestly-labeled manual-verification item."""
    issues = []
    blocks = [b for b in variant.blocks if b.kind == "blocktext"]
    for block in blocks:
        issues.append(Issue(
            category="Dynamic Content", title=f"Dynamic content block reference: {block.text}",
            status=Status.MANUAL_REVIEW, severity=Severity.INFO,
            expected=block.text, location=f"Reference block #{block.order}",
            recommendation="This is a template/merge-tag placeholder from the checklist, not literal "
                            "content — it cannot be compared against static HTML. Verify the resolved "
                            "output directly in the personalization/content-block system.",
            source_rule="Dynamic content block reference (▼BlockText)",
        ))
    return issues
