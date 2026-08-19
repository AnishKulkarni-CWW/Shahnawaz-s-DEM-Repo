"""
FIDELITAS — Rules Engine

Validates the styling actually present in the HTML's links against the
active QA RuleSet. Only checks fields the user has actually configured
(non-None) — an unconfigured rule is not evaluated, never assumed.
"""

import re
from ..models import Issue, Status, Severity, ImplementationModel
from ..rules import RuleSet

FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
BORDER_RADIUS_RE = re.compile(r"border-radius\s*:\s*(\d+(?:\.\d+)?)px", re.I)
BG_COLOR_RE = re.compile(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,8})", re.I)


def _parse_style(style: str) -> dict:
    out = {}
    if not style:
        return out
    m = FONT_SIZE_RE.search(style)
    if m:
        out["font_size"] = float(m.group(1))
    m = BORDER_RADIUS_RE.search(style)
    if m:
        out["border_radius"] = float(m.group(1))
    m = BG_COLOR_RE.search(style)
    if m:
        out["background_color"] = m.group(1).lower()
    return out


def check_cta_rules(impl: ImplementationModel, ruleset: RuleSet) -> list:
    issues = []
    styled_links = [l for l in impl.links if l.style]
    if not styled_links:
        return issues

    has_any_rule = any([
        ruleset.cta_font_size_min_px, ruleset.cta_font_size_max_px,
        ruleset.cta_border_radius_min_px, ruleset.cta_background_color,
    ])
    if not has_any_rule:
        return issues

    for i, link in enumerate(styled_links):
        parsed = _parse_style(link.style)
        label = f"'{link.text[:30]}'" if link.text else f"link #{i+1}"

        if ruleset.cta_font_size_min_px or ruleset.cta_font_size_max_px:
            fs = parsed.get("font_size")
            if fs is None:
                issues.append(Issue(
                    category="CTA Styling", title=f"No inline font-size found on {label}",
                    status=Status.MANUAL_REVIEW, severity=Severity.LOW,
                    recommendation="Font size may be set via an external/embedded stylesheet — verify manually.",
                    source_rule=f"Rule set: {ruleset.name} — CTA font size",
                ))
            else:
                lo = ruleset.cta_font_size_min_px or 0
                hi = ruleset.cta_font_size_max_px or 9999
                if lo <= fs <= hi:
                    issues.append(Issue(
                        category="CTA Styling", title=f"CTA font size within range on {label}",
                        status=Status.PASS, severity=Severity.INFO,
                        actual=f"{fs:g}px", expected=f"{lo}-{hi}px",
                        source_rule=f"Rule set: {ruleset.name} — CTA font size",
                    ))
                else:
                    issues.append(Issue(
                        category="CTA Styling", title=f"CTA font size out of configured range on {label}",
                        status=Status.FAIL, severity=Severity.MEDIUM,
                        actual=f"{fs:g}px", expected=f"{lo}-{hi}px",
                        recommendation="Adjust the CTA font-size to fall within the configured rule range.",
                        source_rule=f"Rule set: {ruleset.name} — CTA font size",
                    ))

        if ruleset.cta_border_radius_min_px:
            br = parsed.get("border_radius")
            if br is None:
                issues.append(Issue(
                    category="CTA Styling", title=f"No inline border-radius found on {label}",
                    status=Status.MANUAL_REVIEW, severity=Severity.LOW,
                    recommendation="Border radius may be set elsewhere — verify manually.",
                    source_rule=f"Rule set: {ruleset.name} — CTA border radius",
                ))
            elif br >= ruleset.cta_border_radius_min_px:
                issues.append(Issue(
                    category="CTA Styling", title=f"CTA border-radius meets minimum on {label}",
                    status=Status.PASS, severity=Severity.INFO,
                    actual=f"{br:g}px", expected=f">= {ruleset.cta_border_radius_min_px}px",
                    source_rule=f"Rule set: {ruleset.name} — CTA border radius",
                ))
            else:
                issues.append(Issue(
                    category="CTA Styling", title=f"CTA border-radius below minimum on {label}",
                    status=Status.FAIL, severity=Severity.LOW,
                    actual=f"{br:g}px", expected=f">= {ruleset.cta_border_radius_min_px}px",
                    recommendation="Increase the border-radius to meet the configured minimum.",
                    source_rule=f"Rule set: {ruleset.name} — CTA border radius",
                ))

        if ruleset.cta_background_color:
            bg = parsed.get("background_color")
            target = ruleset.cta_background_color.lower()
            if bg is None:
                issues.append(Issue(
                    category="CTA Styling", title=f"No inline background-color found on {label}",
                    status=Status.MANUAL_REVIEW, severity=Severity.LOW,
                    recommendation="Background color may be set elsewhere (parent table cell, class) — verify manually.",
                    source_rule=f"Rule set: {ruleset.name} — CTA background color",
                ))
            elif bg == target:
                issues.append(Issue(
                    category="CTA Styling", title=f"CTA background color matches rule on {label}",
                    status=Status.PASS, severity=Severity.INFO,
                    actual=bg, expected=target,
                    source_rule=f"Rule set: {ruleset.name} — CTA background color",
                ))
            else:
                issues.append(Issue(
                    category="CTA Styling", title=f"CTA background color differs from rule on {label}",
                    status=Status.FAIL, severity=Severity.MEDIUM,
                    actual=bg, expected=target,
                    recommendation="Update the CTA background-color to match the configured brand rule.",
                    source_rule=f"Rule set: {ruleset.name} — CTA background color",
                ))

    return issues
