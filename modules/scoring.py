"""
FIDELITAS — Scoring Engine

Computes a category-by-category and overall QA score from the collected
issues. NOT_CHECKED and MANUAL_REVIEW items are excluded from the score
entirely (they are neither a pass nor a fail — scoring them would be
fabricating a result), and are reported separately so nothing is hidden.
"""

from .models import Status, Severity


def compute_scores(issues: list) -> dict:
    by_category = {}
    for issue in issues:
        by_category.setdefault(issue.category, []).append(issue)

    category_scores = {}
    for cat, cat_issues in by_category.items():
        scorable = [i for i in cat_issues if i.status in (Status.PASS, Status.FAIL, Status.WARNING)]
        if not scorable:
            category_scores[cat] = None  # entirely manual/not-checked category
            continue
        max_points = len(scorable) * 5.0
        lost = sum(
            (i.severity.weight if i.status == Status.FAIL else i.severity.weight * 0.4)
            for i in scorable if i.status in (Status.FAIL, Status.WARNING)
        )
        score = max(0.0, (max_points - lost) / max_points) * 100
        category_scores[cat] = round(score, 1)

    numeric_scores = [s for s in category_scores.values() if s is not None]
    overall = round(sum(numeric_scores) / len(numeric_scores), 1) if numeric_scores else None

    counts = {status: sum(1 for i in issues if i.status == status) for status in Status}

    return {
        "overall": overall,
        "by_category": category_scores,
        "counts": counts,
        "total_checks": len(issues),
    }
