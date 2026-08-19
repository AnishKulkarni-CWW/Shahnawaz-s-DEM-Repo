"""
FIDELITAS — core data models.

Every engine in this application returns Issue objects through this shared
vocabulary, so the dashboard, report exporter, and issue manager never need
to know which engine produced a result.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import itertools

_id_counter = itertools.count(1)


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    INFO = "INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NOT_CHECKED = "NOT_CHECKED"

    @property
    def label(self) -> str:
        """Display-layer text — spaces, not the raw enum token, so
        MANUAL_REVIEW / NOT_CHECKED never leak into the UI verbatim."""
        return {
            Status.PASS: "PASS",
            Status.FAIL: "FAIL",
            Status.WARNING: "WARNING",
            Status.INFO: "INFO",
            Status.MANUAL_REVIEW: "MANUAL REVIEW",
            Status.NOT_CHECKED: "NOT CHECKED",
        }[self]

    @property
    def color(self) -> str:
        """Hex value for CSS-driven status chips — brand-authored, not
        dependent on an OS/font-rendered glyph."""
        return {
            Status.PASS: "#22c55e",
            Status.FAIL: "#ef4444",
            Status.WARNING: "#eab308",
            Status.INFO: "#3b82f6",
            Status.MANUAL_REVIEW: "#a855f7",
            Status.NOT_CHECKED: "#6b7280",
        }[self]


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def code(self) -> str:
        """Compact bracket-code form for dense contexts (finding rows,
        narrow report columns)."""
        return {
            Severity.CRITICAL: "SEV-1",
            Severity.HIGH: "SEV-2",
            Severity.MEDIUM: "SEV-3",
            Severity.LOW: "SEV-4",
            Severity.INFO: "SEV-5",
        }[self]

    @property
    def color(self) -> str:
        return {
            Severity.CRITICAL: "#ef4444",
            Severity.HIGH: "#f97316",
            Severity.MEDIUM: "#eab308",
            Severity.LOW: "#3b82f6",
            Severity.INFO: "#6b7280",
        }[self]

    @property
    def weight(self) -> float:
        # used by the scorer — how much one failed check costs
        return {
            Severity.CRITICAL: 5.0,
            Severity.HIGH: 3.0,
            Severity.MEDIUM: 1.5,
            Severity.LOW: 0.5,
            Severity.INFO: 0.0,
        }[self]


@dataclass
class Issue:
    category: str                      # e.g. "ALT Text", "CTA", "Structure"
    title: str                         # short human-readable summary
    status: Status
    severity: Severity = Severity.MEDIUM
    expected: Optional[str] = None
    actual: Optional[str] = None
    difference: Optional[str] = None
    location: Optional[str] = None     # e.g. "Image block #4", "DEM variant 2"
    recommendation: Optional[str] = None
    source_rule: Optional[str] = None  # which checklist item this maps to
    id: int = field(default_factory=lambda: next(_id_counter))
    workflow_status: str = "Open"      # Open -> In Progress -> Fixed -> Recheck -> Passed

    def to_row(self) -> dict:
        return {
            "ID": self.id,
            "Category": self.category,
            "Severity": f"{self.severity.code} — {self.severity.value}",
            "Status": self.status.label,
            "Issue": self.title,
            "Expected": self.expected or "",
            "Actual": self.actual or "",
            "Difference": self.difference or "",
            "Location": self.location or "",
            "Recommendation": self.recommendation or "",
            "Workflow": self.workflow_status,
        }


@dataclass
class ReferenceBlock:
    """One sequential content block extracted from the client checklist
    (DEM(n) sheets): either an ALT-text image block, a CTA block, or the
    mail title."""
    order: int
    kind: str          # "title" | "alt" | "cta"
    text: str
    url: Optional[str] = None


@dataclass
class ReferenceVariant:
    """One DEM/SC variant (e.g. DEM(1)..DEM(5)) parsed from the checklist."""
    name: str
    subject: Optional[str] = None
    directory_url: Optional[str] = None
    blocks: list = field(default_factory=list)  # list[ReferenceBlock]


@dataclass
class ChecklistItem:
    """One row from the 'checklist' or 'Internal_checklist' sheets."""
    number: str
    text_en: str
    text_ja: Optional[str] = None
    dev_status: Optional[str] = None
    source_sheet: str = ""


@dataclass
class ReferenceModel:
    project_name: Optional[str] = None
    variants: list = field(default_factory=list)          # list[ReferenceVariant]
    checklist_items: list = field(default_factory=list)   # list[ChecklistItem]
    image_specs: list = field(default_factory=list)       # list[dict]
    image_size_legend: dict = field(default_factory=dict)  # size code (lowercased) -> "WxH" string


@dataclass
class HtmlImage:
    src: str
    alt: str
    width: Optional[str] = None
    height: Optional[str] = None
    border: Optional[str] = None
    order: int = 0


@dataclass
class HtmlLink:
    href: str
    text: str
    order: int = 0
    style: Optional[str] = None   # raw inline style="" attribute, for rules-engine CTA checks


@dataclass
class ImplementationModel:
    source_name: str           # "Developer HTML", "Live URL", "S3 URL", "Litmus URL"
    raw_html: str = ""
    title: Optional[str] = None
    images: list = field(default_factory=list)   # list[HtmlImage]
    links: list = field(default_factory=list)    # list[HtmlLink]
    text_content: str = ""
    fetch_error: Optional[str] = None
