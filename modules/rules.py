"""
FIDELITAS — QA Rules

Configurable rule sets, editable from the UI without touching code, and
saved as plain JSON so they survive between sessions (per-client rule sets
like "BMW Emailer Rules", "Generic Emailer Rules", etc., as the original
spec asked for).

Any field left as None means "no constraint configured" — the rules engine
skips that check entirely rather than inventing a default threshold, since
a fabricated threshold would produce fabricated pass/fail results.
"""

import os
import json
from dataclasses import dataclass, asdict, field
from typing import Optional

RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa_rules")


@dataclass
class RuleSet:
    name: str = "Generic Emailer Rules"
    cta_font_size_min_px: Optional[int] = None
    cta_font_size_max_px: Optional[int] = None
    cta_border_radius_min_px: Optional[int] = None
    cta_background_color: Optional[str] = None
    spacing_tolerance_px: int = 2
    case_sensitive: bool = True
    japanese_punctuation_strict: bool = True

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return RuleSet(**{k: v for k, v in d.items() if k in RuleSet.__dataclass_fields__})


def ensure_dir():
    os.makedirs(RULES_DIR, exist_ok=True)


def list_rule_sets() -> list:
    ensure_dir()
    names = [f[:-5] for f in os.listdir(RULES_DIR) if f.endswith(".json")]
    if "Generic Emailer Rules" not in names:
        save_rule_set(RuleSet(name="Generic Emailer Rules"))
        names.append("Generic Emailer Rules")
    return sorted(names)


def load_rule_set(name: str) -> RuleSet:
    ensure_dir()
    path = os.path.join(RULES_DIR, f"{name}.json")
    if not os.path.exists(path):
        return RuleSet(name=name)
    with open(path, "r", encoding="utf-8") as f:
        return RuleSet.from_dict(json.load(f))


def save_rule_set(rule_set: RuleSet):
    ensure_dir()
    path = os.path.join(RULES_DIR, f"{rule_set.name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rule_set.to_dict(), f, ensure_ascii=False, indent=2)


def delete_rule_set(name: str):
    path = os.path.join(RULES_DIR, f"{name}.json")
    if os.path.exists(path) and name != "Generic Emailer Rules":
        os.remove(path)
