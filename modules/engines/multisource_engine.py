"""
FIDELITAS — Multi-Source Consistency Engine

Compares the developer HTML (treated as the implementation baseline) against
whichever of Live / S3 / Litmus URLs were successfully fetched, checking
that image counts, ALT texts, and link counts stay consistent across
environments. If a source could not be fetched, that is reported honestly
instead of being silently excluded from the score.

source_rule is deliberately phrased per-source ("Check Mail Format: Live
URL", etc.) rather than one generic label — this is what lets these
findings reconcile against a checklist item that literally lists "Live
URL: / Litmus URL: / Amazon S3 Path:" as its own checkpoints, instead of
that checkpoint showing no evidence at all.
"""

from ..models import Issue, Status, Severity, ImplementationModel
from . import text_diff


def compare_sources(baseline: ImplementationModel, others: list) -> list:
    issues = []
    for other in others:
        rule = f"Check Mail Format: {other.source_name}"
        if other.fetch_error:
            issues.append(Issue(
                category="Multi-Source", title=f"{other.source_name} could not be retrieved",
                status=Status.NOT_CHECKED, severity=Severity.MEDIUM,
                actual=other.fetch_error,
                recommendation="Confirm the URL is correct and publicly reachable, or verify manually.",
                source_rule=rule,
            ))
            continue

        # Image count
        if len(baseline.images) != len(other.images):
            issues.append(Issue(
                category="Multi-Source", title=f"Image count differs between HTML and {other.source_name}",
                status=Status.FAIL, severity=Severity.HIGH,
                expected=str(len(baseline.images)), actual=str(len(other.images)),
                location=other.source_name,
                recommendation=f"Check that {other.source_name} was updated with the latest HTML.",
                source_rule=rule,
            ))
        else:
            issues.append(Issue(
                category="Multi-Source", title=f"Image count matches between HTML and {other.source_name}",
                status=Status.PASS, severity=Severity.INFO,
                location=other.source_name,
                source_rule=rule,
            ))

        # ALT text consistency, position by position
        mismatched_alts = 0
        for i in range(min(len(baseline.images), len(other.images))):
            if baseline.images[i].alt.strip() != other.images[i].alt.strip():
                mismatched_alts += 1
        if mismatched_alts:
            issues.append(Issue(
                category="Multi-Source", title=f"{mismatched_alts} ALT text mismatch(es) vs {other.source_name}",
                status=Status.FAIL, severity=Severity.MEDIUM,
                location=other.source_name,
                recommendation=f"{other.source_name} appears to be running an older/different HTML build.",
                source_rule=rule,
            ))
        elif baseline.images:
            issues.append(Issue(
                category="Multi-Source", title=f"ALT text matches between HTML and {other.source_name}",
                status=Status.PASS, severity=Severity.INFO,
                location=other.source_name,
                source_rule=rule,
            ))

        # Link count
        if len(baseline.links) != len(other.links):
            issues.append(Issue(
                category="Multi-Source", title=f"Link count differs between HTML and {other.source_name}",
                status=Status.WARNING, severity=Severity.MEDIUM,
                expected=str(len(baseline.links)), actual=str(len(other.links)),
                location=other.source_name,
                source_rule=rule,
            ))
        else:
            issues.append(Issue(
                category="Multi-Source", title=f"Link count matches between HTML and {other.source_name}",
                status=Status.PASS, severity=Severity.INFO,
                location=other.source_name,
                source_rule=rule,
            ))

    return issues
