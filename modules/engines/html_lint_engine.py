"""
FIDELITAS — HTML Structure Lint Engine

Static, deterministic HTML checks that don't require rendering:
  - DOCTYPE / charset meta presence
  - duplicate id attributes
  - a best-effort tag-balance heuristic for common block tags (this is
    explicitly NOT a full W3C validator — labeled as a heuristic so it's
    never mistaken for one)
  - external stylesheet usage (unreliable across email clients)
  - responsive-QA proxies: viewport meta tag and @media query presence
    (a real render is still needed for true responsive verification —
    these are presence signals only, and are labeled as such)
"""

import re
from bs4 import BeautifulSoup
from ..models import Issue, Status, Severity, ImplementationModel

# tags where an unclosed/mismatched instance is a meaningful signal in
# email HTML specifically (table-based layouts make table/tr/td the most
# common source of real bugs)
BALANCE_TAGS = ["table", "tr", "td", "div", "span", "p"]


def run_lint(impl: ImplementationModel) -> list:
    issues = []
    raw = impl.raw_html or ""
    soup = BeautifulSoup(raw, "html.parser")

    # --- DOCTYPE ---
    if re.match(r"\s*<!DOCTYPE", raw, re.I):
        issues.append(Issue(
            category="HTML Structure", title="DOCTYPE declaration present",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="HTML structure — DOCTYPE",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No DOCTYPE declaration found",
            status=Status.WARNING, severity=Severity.LOW,
            recommendation="Add a DOCTYPE — several email clients fall back to quirks-mode rendering without one.",
            source_rule="HTML structure — DOCTYPE",
        ))

    # --- charset ---
    charset_tag = soup.find("meta", attrs={"charset": True}) or soup.find(
        "meta", attrs={"http-equiv": re.compile("content-type", re.I)})
    if charset_tag:
        issues.append(Issue(
            category="HTML Structure", title="Character encoding meta tag present",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="HTML structure — charset",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No character-encoding meta tag found",
            status=Status.FAIL, severity=Severity.HIGH,
            recommendation='Add <meta charset="UTF-8"> — without it, Japanese text can render as mojibake in some clients.',
            source_rule="HTML structure — charset",
        ))

    # --- duplicate IDs ---
    ids = [tag.get("id") for tag in soup.find_all(attrs={"id": True})]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        issues.append(Issue(
            category="HTML Structure", title=f"{len(dupes)} duplicate id attribute(s) found",
            status=Status.FAIL, severity=Severity.MEDIUM,
            actual=", ".join(sorted(dupes)),
            recommendation="IDs must be unique — duplicates can break anchor links and client-side targeting.",
            source_rule="HTML structure — duplicate IDs",
        ))
    elif ids:
        issues.append(Issue(
            category="HTML Structure", title="No duplicate id attributes found",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="HTML structure — duplicate IDs",
        ))

    # --- tag balance heuristic (NOT a full validator) ---
    imbalanced = []
    for tag in BALANCE_TAGS:
        opens = len(re.findall(rf"<{tag}[\s>]", raw, re.I))
        closes = len(re.findall(rf"</{tag}\s*>", raw, re.I))
        if opens != closes:
            imbalanced.append(f"<{tag}>: {opens} opening vs {closes} closing")
    if imbalanced:
        issues.append(Issue(
            category="HTML Structure", title="Possible unclosed/mismatched tags detected",
            status=Status.WARNING, severity=Severity.MEDIUM,
            actual="; ".join(imbalanced),
            recommendation="This is a best-effort tag-count heuristic, not a full markup validator — confirm with a proper HTML validator before treating as confirmed.",
            source_rule="HTML structure — tag balance (heuristic)",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No obvious tag-balance issues detected (heuristic check)",
            status=Status.PASS, severity=Severity.INFO,
            recommendation="This is a best-effort heuristic, not a full markup validator.",
            source_rule="HTML structure — tag balance (heuristic)",
        ))

    # --- external stylesheet usage ---
    external_css = soup.find_all("link", attrs={"rel": re.compile("stylesheet", re.I)})
    if external_css:
        issues.append(Issue(
            category="HTML Structure", title=f"{len(external_css)} external stylesheet link(s) found",
            status=Status.WARNING, severity=Severity.MEDIUM,
            actual="; ".join(l.get("href", "") for l in external_css),
            recommendation="Many email clients (Gmail, Outlook) strip external stylesheets — inline critical CSS instead.",
            source_rule="Email HTML — inline vs external CSS",
        ))
    else:
        issues.append(Issue(
            category="HTML Structure", title="No external stylesheets found",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Email HTML — inline vs external CSS",
        ))

    # --- responsive proxy checks (presence only, not a real render) ---
    viewport = soup.find("meta", attrs={"name": "viewport"})
    issues.append(Issue(
        category="Responsive", title="Viewport meta tag present" if viewport else "No viewport meta tag found",
        status=Status.PASS if viewport else Status.INFO,
        severity=Severity.INFO if viewport else Severity.LOW,
        recommendation=None if viewport else "Not always required for table-based emailers, but confirm mobile behavior manually.",
        source_rule="Responsive QA — viewport presence (proxy check, not a real render)",
    ))
    has_media_query = bool(re.search(r"@media", raw))
    issues.append(Issue(
        category="Responsive", title="Media query block(s) present in HTML" if has_media_query else "No @media query blocks found",
        status=Status.INFO,
        severity=Severity.INFO,
        recommendation="Presence of @media rules is only a signal that responsive styling was attempted — actual behavior still needs manual verification across real devices/clients." if has_media_query
                       else "No responsive breakpoints detected — confirm whether this template is intentionally fixed-width.",
        source_rule="Responsive QA — media query presence (proxy check, not a real render)",
    ))

    # --- every link, empty/placeholder href — independent of reference
    # matching, so a broken link that doesn't correspond to any checklist
    # CTA still gets caught rather than silently falling into "unmatched". ---
    broken_href_links = [(i, l) for i, l in enumerate(impl.links) if not l.href or l.href.strip() in ("#", "")]
    if broken_href_links:
        issues.append(Issue(
            category="Links", title=f"{len(broken_href_links)} link(s) have an empty or placeholder href",
            status=Status.FAIL, severity=Severity.CRITICAL,
            actual="; ".join(f"'{l.text[:30]}'" if l.text else f"link #{i+1}" for i, l in broken_href_links),
            recommendation="These links will not navigate anywhere in a live email — set real destination URLs.",
            source_rule="Link integrity — every link, independent of reference matching",
        ))
    elif impl.links:
        issues.append(Issue(
            category="Links", title="No links with an empty or placeholder href found",
            status=Status.PASS, severity=Severity.INFO,
            source_rule="Link integrity — every link, independent of reference matching",
        ))

    return issues
