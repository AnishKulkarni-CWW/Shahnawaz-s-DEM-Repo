"""
FIDELITAS — Technical / Structural Engine

Runs the deterministic checks that correspond to the "Internal_checklist"
dev QA items (border=0, ALT presence, 600px width, forbidden CSS patterns,
mirror-page include tag, AWS-hosted images, footer link styling, etc.)
directly against the parsed HTML.

Every checklist item that was parsed from the workbook is reconciled here:
if we ran an automated check for it, its result is attached; if not, it is
explicitly marked MANUAL_REVIEW rather than silently dropped or assumed to
pass — per the "never fake a result" requirement.
"""

import re
import datetime as _dt
from ..models import Issue, Status, Severity, ImplementationModel, ChecklistItem
from . import text_diff

FORBIDDEN_CSS_SNIPPETS = [
    "a{color: #FFFFFF!important}",
    ".white-text a{color: #FFFFFF",
]

TARGET_WIDTH_PX = "600"
AWS_HOST_HINTS = ["bmw-static.com", "s3.amazonaws.com", "cloudfront.net", "static.com"]


def run_html_structure_checks(impl: ImplementationModel) -> list:
    issues = []
    raw = impl.raw_html or ""

    # --- border="0" on every image ---
    missing_border = [i for i, img in enumerate(impl.images) if img.border not in ("0", 0)]
    if impl.images:
        if not missing_border:
            issues.append(Issue(
                category="HTML Structure", title='All images use border="0"',
                status=Status.PASS, severity=Severity.INFO,
                source_rule='Use border="0" for all images.',
            ))
        else:
            issues.append(Issue(
                category="HTML Structure", title=f'{len(missing_border)} image(s) missing border="0"',
                status=Status.FAIL, severity=Severity.MEDIUM,
                location=f"HTML image(s) #{[i+1 for i in missing_border]}",
                recommendation='Add border="0" to every <img> tag to prevent blue borders in Outlook.',
                source_rule='Use border="0" for all images.',
            ))

    # --- ALT presence & no forced line-break ---
    empty_alt = [i for i, img in enumerate(impl.images) if not img.alt.strip()]
    if empty_alt:
        issues.append(Issue(
            category="ALT Text", title=f"{len(empty_alt)} image(s) have empty ALT attributes",
            status=Status.FAIL, severity=Severity.HIGH,
            location=f"HTML image(s) #{[i+1 for i in empty_alt]}",
            recommendation="Every content image needs ALT text per the client checklist — add the reference text.",
            source_rule="Check Alt text - For image (pic/text)",
        ))
    elif impl.images:
        issues.append(Issue(
            category="ALT Text", title="All images have ALT text present",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Check Alt text - For image (pic/text)",
        ))
    newline_alt = [i for i, img in enumerate(impl.images) if "\n" in (img.alt or "")]
    if newline_alt:
        issues.append(Issue(
            category="ALT Text", title=f"{len(newline_alt)} image(s) have ALT text containing a line break",
            status=Status.FAIL, severity=Severity.MEDIUM,
            location=f"HTML image(s) #{[i+1 for i in newline_alt]}",
            recommendation="ALT text must not break into a new line — check the alt=\"\" attribute for embedded newlines.",
            source_rule="Alt should not come in new line",
        ))
    elif impl.images:
        issues.append(Issue(
            category="ALT Text", title="No ALT text contains a forced line break",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Alt should not come in new line",
        ))

    # --- Email width 600px ---
    width_match = re.search(r'width\s*[:=]\s*["\']?(\d+)(px)?["\']?', raw)
    if width_match:
        found_width = width_match.group(1)
        # look specifically for a 600 occurring near the top of the document (outer table)
        if TARGET_WIDTH_PX in raw[:3000]:
            issues.append(Issue(
                category="HTML Structure", title="Emailer outer width appears to be 600px",
                status=Status.PASS, severity=Severity.INFO,
                source_rule='Check emailer width - 600px width (CO.JP)',
            ))
        else:
            issues.append(Issue(
                category="HTML Structure", title="Could not confirm 600px outer table width near document start",
                status=Status.WARNING, severity=Severity.MEDIUM,
                actual=f"First width found: {found_width}px",
                recommendation="Manually confirm the outer container table is exactly 600px wide.",
                source_rule='Check emailer width - 600px width (CO.JP)',
            ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No explicit width attribute found",
            status=Status.MANUAL_REVIEW, severity=Severity.MEDIUM,
            recommendation="Confirm the outer table width manually — no width attribute/style was detected.",
            source_rule='Check emailer width - 600px width (CO.JP)',
        ))

    # --- Mirror page include tag ---
    if "bmwJPMINIMirrorPage" in raw:
        issues.append(Issue(
            category="HTML Structure", title="Mirror page include tag present",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Check index file for presence of Mirror Page Code",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="Mirror page include tag not found",
            status=Status.WARNING, severity=Severity.MEDIUM,
            recommendation="Confirm whether this template requires the <%@ include view='bmwJPMINIMirrorPage' %> tag.",
            source_rule="Check index file for presence of Mirror Page Code",
        ))

    # --- forbidden CSS patterns ---
    found_forbidden = [snip for snip in FORBIDDEN_CSS_SNIPPETS if snip in raw]
    if found_forbidden:
        issues.append(Issue(
            category="HTML Structure", title="Forbidden CSS pattern(s) found",
            status=Status.FAIL, severity=Severity.MEDIUM,
            actual="; ".join(found_forbidden),
            recommendation="Remove this CSS — it is explicitly disallowed per the client's technical checklist.",
            source_rule="Check displayed code not required",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No forbidden CSS patterns detected",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Check displayed code not required",
        ))

    # --- images loaded from an approved static/AWS host ---
    if impl.images:
        off_host = [i for i, img in enumerate(impl.images)
                    if img.src and not any(h in img.src for h in AWS_HOST_HINTS) and img.src.startswith("http")]
        if off_host:
            issues.append(Issue(
                category="Images", title=f"{len(off_host)} image(s) not served from an approved static/AWS host",
                status=Status.WARNING, severity=Severity.HIGH,
                location=f"HTML image(s) #{[i+1 for i in off_host]}",
                actual="; ".join(impl.images[i].src for i in off_host[:5]),
                recommendation="Confirm these images are being served from the approved AWS/static hosting domain.",
                source_rule="Is the image loaded from the AWS server?",
            ))
        else:
            issues.append(Issue(
                category="Images", title="All images appear to be served from an approved host",
                status=Status.PASS, severity=Severity.INFO,
                source_rule="Is the image loaded from the AWS server?",
            ))

    # --- unnecessary line breaks / double spaces across the whole body text ---
    body_sp_issues = text_diff.spacing_issues(impl.text_content)
    if body_sp_issues:
        issues.append(Issue(
            category="Spacing", title="Unnecessary spacing/line-break patterns found in body text",
            status=Status.WARNING, severity=Severity.LOW,
            actual=", ".join(body_sp_issues),
            recommendation="Review the flagged sections for stray double spaces or blank lines.",
            source_rule="Are there any unnecessary line breaks or spaces?",
        ))
    else:
        issues.append(Issue(
            category="Spacing", title="No obvious stray spacing/line-break issues detected",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Are there any unnecessary line breaks or spaces?",
        ))

    # --- unsubscribe / footer presence (keyword heuristic) ---
    footer_keywords = ["配信停止", "unsubscribe", "©", "all rights reserved"]
    if any(k.lower() in raw.lower() for k in footer_keywords):
        issues.append(Issue(
            category="HTML Structure", title="Footer/unsubscribe block appears present",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Check for UNSUBSCIBE button, address and Year change",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No unsubscribe/footer keywords detected",
            status=Status.WARNING, severity=Severity.HIGH,
            recommendation="Confirm the footer contains the unsubscribe link, address block, and current year.",
            source_rule="Check for UNSUBSCIBE button, address and Year change",
        ))

    # --- footer year currency: a stale copy-pasted footer is a very common
    # real defect ("© 2023" left over in a 2026 send) ---
    footer_zone = impl.text_content[-600:] if impl.text_content else ""
    years_found = sorted(set(int(y) for y in re.findall(r"\b(20\d{2})\b", footer_zone)))
    current_year = _dt.datetime.now().year
    if years_found:
        stale = [y for y in years_found if y < current_year - 1]
        if stale:
            issues.append(Issue(
                category="HTML Structure", title="Footer year looks stale",
                status=Status.WARNING, severity=Severity.MEDIUM,
                actual=", ".join(str(y) for y in stale), expected=f"{current_year} (or {current_year-1})",
                location="Footer (last ~600 characters of visible text)",
                recommendation="Confirm this copyright/footer year was actually updated for this send, not carried over from an older template.",
                source_rule="Check for UNSUBSCIBE button, address and Year change",
            ))
        else:
            issues.append(Issue(
                category="HTML Structure", title="Footer year appears current",
                status=Status.PASS, severity=Severity.INFO,
                actual=", ".join(str(y) for y in years_found),
                source_rule="Check for UNSUBSCIBE button, address and Year change",
            ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No 4-digit year found in the footer area to verify",
            status=Status.MANUAL_REVIEW, severity=Severity.LOW,
            recommendation="Confirm manually whether a copyright/footer year is expected here and current.",
            source_rule="Check for UNSUBSCIBE button, address and Year change",
        ))

    # --- footer junk characters (common PSD-copy-paste artifact) ---
    junk_pattern = re.compile(r"[\ufffd\u25a1]|(.)\1{4,}")  # replacement char, tofu box, or 5+ repeated chars
    junk_hits = junk_pattern.findall(footer_zone)
    if junk_hits:
        issues.append(Issue(
            category="HTML Structure", title="Possible junk character(s) in footer text",
            status=Status.WARNING, severity=Severity.MEDIUM,
            location="Footer (last ~600 characters of visible text)",
            recommendation="Common artifact of copy-pasting from a PSD/design file — inspect the raw footer text directly.",
            source_rule="Check common error: junk characters in footer",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No obvious junk characters detected in footer text",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Check common error: junk characters in footer",
        ))

    # --- preview/preheader text: the hidden snippet email clients show next
    # to the subject line. Detected as a short text block near the very
    # start of <body> that's visually hidden (display:none / font-size:0 /
    # zero-height), which is the standard preheader implementation pattern. ---
    body_start = raw[re.search(r"<body", raw, re.I).start():] if re.search(r"<body", raw, re.I) else raw
    preheader_zone = body_start[:1500]
    hidden_span = re.search(
        r'<(?:div|span)[^>]*style="[^"]*(?:display\s*:\s*none|font-size\s*:\s*0|max-height\s*:\s*0)[^"]*"[^>]*>([^<]{3,})<',
        preheader_zone, re.I,
    )
    if hidden_span and hidden_span.group(1).strip():
        issues.append(Issue(
            category="HTML Structure", title="Preview/preheader text found near top of body",
            status=Status.PASS, severity=Severity.INFO,
            actual=hidden_span.group(1).strip()[:80],
            source_rule="Check preview text at the TOP in all clients",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No hidden preview/preheader text pattern detected near top of body",
            status=Status.MANUAL_REVIEW, severity=Severity.LOW,
            recommendation="Preheader implementations vary — if this template genuinely uses one, verify its text and visibility settings directly; this pattern-match may simply not fit this template's markup.",
            source_rule="Check preview text at the TOP in all clients",
        ))

    # --- links wrapping a whole image with no CTA button text — the
    # checklist explicitly wants CTA-only links except for a named library
    # exception, which this tool can't identify on its own, so it's
    # surfaced for confirmation rather than failed outright. ---
    whole_image_links = [i for i, l in enumerate(impl.links) if l.text.startswith("[image:")]
    if whole_image_links:
        issues.append(Issue(
            category="HTML Structure", title=f"{len(whole_image_links)} link(s) wrap an entire image with no separate CTA text",
            status=Status.MANUAL_REVIEW, severity=Severity.LOW,
            location=f"HTML link(s) #{[i+1 for i in whole_image_links]}",
            recommendation="Confirm each of these is the named 'library section' exception — otherwise, only the CTA element itself should be linked, not the full banner image.",
            source_rule="Give links to CTA only, not to banner image",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No links found wrapping an entire image without CTA text",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Give links to CTA only, not to banner image",
        ))

    return issues


# Checklist items we genuinely cannot verify without a real browser / email
# rendering engine, an ESP connection, or the original PSD — these are named
# explicitly rather than silently skipped.
_MANUAL_ONLY_KEYWORDS = [
    "litmus", "dark mode", "aspect ratio", "spacer.gif",
    "preview code", "collapse when viewed", "崩れ",
    "latest file should be uploaded", "adebis url must be updated",
    "web based, desktop and mobile",
]


def _match_checklist_item(item: ChecklistItem, automated_by_rule: dict) -> dict:
    """Core matching logic, shared by the flat reconciliation (used for
    scoring/CSV export) and the grouped view (used by the checklist-first
    UI) so the two can never silently disagree with each other. Returns
    {"status": Status, "supporting": list[Issue], "reason": str}."""
    if item.dev_status and str(item.dev_status).strip().upper() in ("NA", "N/A"):
        return {"status": Status.INFO, "supporting": [],
                "reason": "Marked N/A for this campaign in the checklist's own Dev Status column — not a gap."}

    matched = []
    for rule_text, matches in automated_by_rule.items():
        if _fuzzy_contains(item.text_en, rule_text):
            matched.extend(matches)

    is_manual_only = any(k in item.text_en.lower() for k in _MANUAL_ONLY_KEYWORDS)

    if is_manual_only:
        # Explicitly known to require external/manual verification — takes
        # priority even if an automated check loosely overlaps in keywords
        # (e.g. "latest file uploaded to AWS" sharing "AWS server" with the
        # unrelated "images hosted on AWS" check would otherwise silently
        # produce a false PASS on a freshness claim this tool can't verify).
        return {"status": Status.MANUAL_REVIEW, "supporting": matched,
                "reason": "This check requires real browser/email-client rendering, ESP access, or the original design file — not verifiable from static HTML alone."}
    if matched:
        return {"status": _worst_status(matched), "supporting": matched, "reason": None}
    return {"status": Status.NOT_CHECKED, "supporting": [],
            "reason": "No automated check currently implemented for this item — add a module or verify manually."}


def reconcile_checklist_items(checklist_items: list, automated_issues: list) -> list:
    """Flat Issue list — one per checklist item — used for overall scoring
    and CSV/Excel/PDF export rows. See build_checklist_groups() for the
    richer structure (item + its actual supporting evidence) used by the
    checklist-first UI."""
    out = []
    automated_by_rule = {}
    for issue in automated_issues:
        if issue.source_rule:
            automated_by_rule.setdefault(issue.source_rule, []).append(issue)

    for item in checklist_items:
        result = _match_checklist_item(item, automated_by_rule)
        status = result["status"]
        out.append(Issue(
            category="Checklist Item", title=item.text_en,
            status=status, severity=Severity.MEDIUM if status == Status.FAIL else Severity.INFO,
            recommendation=result["reason"] if result["reason"] else (
                None if status == Status.PASS else "See linked automated finding(s) above for detail."),
            source_rule=f"Checklist #{item.number} ({item.source_sheet})",
        ))
    return out


def build_checklist_groups(checklist_items: list, automated_issues: list) -> list:
    """Returns one dict per checklist item: {"item": ChecklistItem,
    "status": Status, "supporting": list[Issue]} — the actual underlying
    findings that produced the status, for a checklist-item-first UI where
    the checklist IS the primary structure and engine-level findings are
    nested evidence underneath it, rather than a separate parallel list."""
    automated_by_rule = {}
    for issue in automated_issues:
        if issue.source_rule:
            automated_by_rule.setdefault(issue.source_rule, []).append(issue)

    groups = []
    for item in checklist_items:
        result = _match_checklist_item(item, automated_by_rule)
        groups.append({
            "item": item,
            "status": result["status"],
            "reason": result["reason"],
            "supporting": result["supporting"],
        })
    return groups


_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "should", "must",
    "check", "use", "are", "not", "all", "any", "its", "top", "new", "one",
    "your", "you", "can", "has", "have", "been", "will", "per", "each",
}

# Words common enough across MANY different QA concepts that a single
# shared hit isn't a reliable signal on its own (e.g. "image" appears in
# checks about ALT text, dimensions, AWS hosting, and aspect ratio alike —
# matching on it alone would wrongly conflate all of them). A shared word
# NOT in this set is treated as distinctive enough to count by itself.
_GENERIC_DOMAIN_WORDS = {
    "image", "images", "text", "link", "links", "file", "files", "email",
    "mail", "html", "content", "size", "code", "page", "client", "clients",
    "cta", "url", "urls", "button",
    # words this tool's OWN source_rule strings reuse repeatedly as internal
    # methodology vocabulary (e.g. "X presence check", "HTML structure —
    # Y") — a checklist item using one of these in its ordinary English
    # sense would otherwise falsely overlap with many unrelated buckets
    # that only share the word because of this tool's own naming habits,
    # not genuine topical relevance. Found empirically: "presence" alone
    # pulled 5 unrelated buckets (viewport/media-query/PPTX presence
    # checks) into a checklist item that was really just asking about the
    # mirror-page tag.
    "presence", "structure", "correctly", "pptx", "reference", "integrity",
    "consistency", "responsive", "proxy", "real",
}


def _significant_words(s: str) -> set:
    words = re.findall(r"[a-zA-Z]{3,}", (s or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _fuzzy_contains(a: str, b: str) -> bool:
    """True if two check descriptions are plausibly about the same thing.
    Combines an exact-prefix check (works well when the checklist's own
    wording was used to write source_rule, e.g. copied verbatim from one
    specific workbook) with a keyword-overlap check (needed for a
    DIFFERENT checklist file using different phrasing for the same
    underlying concept — e.g. "Check Alt text - For image (pic)" vs this
    tool's own "ALT text presence"). A single shared DISTINCTIVE word (like
    "alt", "adebis", "spacer", "litmus") is enough; a single shared GENERIC
    word (like "image", "text", "file") is not — that was the source of a
    real false-positive during testing (an unrelated AWS-hosting check
    wrongly claimed a PSD-aspect-ratio item, sharing only the word
    "image") — so generic-only overlap requires at least two matches."""
    a_l, b_l = (a or "").lower(), (b or "").lower()
    if a_l[:20] in b_l or b_l[:20] in a_l or a_l == b_l:
        return True
    wa, wb = _significant_words(a), _significant_words(b)
    overlap = wa & wb
    if not overlap:
        return False
    if overlap - _GENERIC_DOMAIN_WORDS:
        return True
    return len(overlap) >= 2


def _worst_status(issues: list) -> Status:
    order = [Status.FAIL, Status.WARNING, Status.MANUAL_REVIEW, Status.INFO, Status.PASS]
    for s in order:
        if any(i.status == s for i in issues):
            return s
    return Status.NOT_CHECKED
