"""
FIDELITAS — Audit History Store

Appends one JSON line per completed audit to a local file (no external
service — consistent with the "keep processing local" security
requirement). Powers two things from the original spec:
  - History: a trend of scores over time for a given project+variant
  - Re-audit: automatic "vs last audit" delta on the dashboard
"""

import os
import json
from datetime import datetime

HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fidelitas_data")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.jsonl")


def _ensure():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, "a").close()


def record_run(project_name: str, variant: str, overall_score, counts: dict, total_checks: int):
    _ensure()
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "project_name": project_name or "Unknown Project",
        "variant": variant,
        "overall_score": overall_score,
        "counts": {k.value if hasattr(k, "value") else str(k): v for k, v in counts.items()},
        "total_checks": total_checks,
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def get_history(project_name: str, variant: str) -> list:
    _ensure()
    out = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("project_name") == (project_name or "Unknown Project") and entry.get("variant") == variant:
                out.append(entry)
    return sorted(out, key=lambda e: e["timestamp"])


def get_last_score(project_name: str, variant: str):
    """Most recent prior run's overall score, or None if there isn't one yet."""
    hist = get_history(project_name, variant)
    if not hist:
        return None
    return hist[-1].get("overall_score")
