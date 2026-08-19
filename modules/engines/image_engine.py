"""
FIDELITAS — Image QA Engine

Two tiers of checking:

1. Always on, no network needed:
   - duplicate `src` detection
   - empty/missing `src`
   - declared width/height vs the client's images（AEM）spec sheet
     (matched by filename substring)
   - cross-check between a spec row's size CODE (e.g. "xl") and its
     notes-embedded dimension against the "Image size" legend sheet —
     catches the checklist itself being internally inconsistent, and
     provides a dimension fallback when a row's notes field has no
     directly-extractable WxH pattern

2. Opt-in (`verify_remote_images`), because it makes real HTTP requests:
   - actually fetches each image and reads real pixel dimensions + file
     size with Pillow, compares against the declared <img> attributes
     (catches "declared 300x200 but the file itself is 600x400" bugs)
   - compares real file size against the spec's target file-size range
     (the checklist's "100～150KB" style budget — parsed but previously
     never actually enforced)
   - flags genuinely broken/unreachable images with the real error,
     never a fabricated status
"""

import re
import io
from ..models import Issue, Status, Severity, ImplementationModel


def _parse_dimensions(dim_str):
    """'890x501' or '890×501' (possibly embedded in other text) -> (890, 501)"""
    if not dim_str:
        return None
    m = re.search(r"(\d+)\s*[x×]\s*(\d+)", str(dim_str))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _parse_size_range_kb(size_str):
    """'100～150KB' / '50-150KB' / '~100KB' -> (min_kb, max_kb) best effort.
    Handles the full-width tilde (～) used throughout the source checklist —
    re.findall on digits doesn't care what separator sits between them."""
    if not size_str:
        return None
    nums = [int(n) for n in re.findall(r"\d+", str(size_str))]
    if not nums:
        return None
    if len(nums) == 1:
        return (0, nums[0])
    return (min(nums), max(nums))


def _find_spec(img_src: str, image_specs: list):
    if not image_specs:
        return None, None
    filename = img_src.rstrip("/").split("/")[-1]
    spec = next((s for s in image_specs if s.get("filename") and s["filename"] in filename), None)
    return spec, filename


def _resolve_spec_dimensions(spec: dict, legend: dict):
    """Returns (effective_dims, legend_mismatch_note). effective_dims is the
    dimension to actually check the HTML against — the notes-embedded value
    if present and it agrees with the legend (or the legend has no entry for
    this code), else the legend value is used as a fallback. If the two
    genuinely disagree, that disagreement is returned as its own finding
    rather than silently picking one."""
    notes_dims = _parse_dimensions(spec.get("dimensions"))
    code = (spec.get("code") or "").strip().lower()
    legend_dims = _parse_dimensions(legend.get(code)) if legend and code in legend else None

    if notes_dims and legend_dims and notes_dims != legend_dims:
        return notes_dims, (
            f"size code '{spec.get('code')}' maps to {legend_dims[0]}x{legend_dims[1]} in the "
            f"Image size legend, but this row's own notes say {notes_dims[0]}x{notes_dims[1]}"
        )
    if notes_dims:
        return notes_dims, None
    if legend_dims:
        return legend_dims, None
    return None, None


def check_image_specs(impl: ImplementationModel, image_specs: list, image_size_legend: dict = None) -> list:
    issues = []
    legend = image_size_legend or {}
    if not impl.images:
        return issues

    # --- duplicate / empty src ---
    seen = {}
    for i, img in enumerate(impl.images):
        if not img.src.strip():
            issues.append(Issue(
                category="Images", title="Image has an empty src attribute",
                status=Status.FAIL, severity=Severity.CRITICAL,
                location=f"HTML image #{i+1}",
                recommendation="This image will render broken in every client — set a valid src.",
                source_rule="Image integrity",
            ))
            continue
        seen.setdefault(img.src, []).append(i)
    dupes = {src: idxs for src, idxs in seen.items() if len(idxs) > 1}
    for src, idxs in dupes.items():
        issues.append(Issue(
            category="Images", title=f"Same image used {len(idxs)} times",
            status=Status.INFO, severity=Severity.LOW,
            actual=src, location=f"HTML image(s) #{[i+1 for i in idxs]}",
            recommendation="Confirm this repetition is intentional.",
            source_rule="Image integrity",
        ))

    # --- declared dimensions vs client spec sheet, legend cross-checked ---
    if image_specs:
        for i, img in enumerate(impl.images):
            spec, filename = _find_spec(img.src, image_specs)
            if not spec:
                continue

            spec_dims, legend_mismatch = _resolve_spec_dimensions(spec, legend)
            if legend_mismatch:
                issues.append(Issue(
                    category="Images", title="Checklist spec sheet is internally inconsistent for this image",
                    status=Status.WARNING, severity=Severity.LOW,
                    actual=legend_mismatch, location=f"Spec row for {filename}",
                    recommendation="Flag this to whoever maintains the checklist — the size code and the "
                                    "stated dimensions disagree with each other, independent of the HTML.",
                    source_rule="Image spec internal consistency (vs. Image size legend)",
                ))

            if spec_dims and img.width and img.height:
                try:
                    declared = (int(img.width), int(img.height))
                except ValueError:
                    declared = None
                if declared and declared != spec_dims:
                    issues.append(Issue(
                        category="Images", title="Image dimensions differ from client spec",
                        status=Status.FAIL, severity=Severity.HIGH,
                        expected=f"{spec_dims[0]}x{spec_dims[1]}", actual=f"{declared[0]}x{declared[1]}",
                        location=f"HTML image #{i+1} ({filename})",
                        recommendation=f"Resize to match the spec sheet ({spec.get('code', 'size code n/a')}).",
                        source_rule="Image dimension spec match",
                    ))
                elif declared:
                    issues.append(Issue(
                        category="Images", title="Image dimensions match client spec",
                        status=Status.PASS, severity=Severity.INFO,
                        location=f"HTML image #{i+1} ({filename})",
                        source_rule="Image dimension spec match",
                    ))

    return issues


def verify_remote_images(impl: ImplementationModel, image_specs: list = None, max_images: int = 25, verify_ssl: bool = True) -> list:
    """Opt-in: actually fetches each image over HTTP and inspects real bytes,
    including — where a spec row matches by filename — the real file size
    against the checklist's stated KB budget."""
    import requests
    from PIL import Image

    issues = []
    image_specs = image_specs or []
    candidates = [(i, img) for i, img in enumerate(impl.images) if img.src.startswith("http")]
    skipped = len(impl.images) - len(candidates)

    for i, img in candidates[:max_images]:
        try:
            resp = requests.get(img.src, timeout=10, verify=verify_ssl,
                                 headers={"User-Agent": "Mozilla/5.0 (FIDELITAS QA Auditor)"})
            resp.raise_for_status()
            content = resp.content
            real_kb = len(content) / 1024

            try:
                pil_img = Image.open(io.BytesIO(content))
                real_w, real_h = pil_img.size
            except Exception:
                issues.append(Issue(
                    category="Images", title="Image URL did not return a readable image",
                    status=Status.FAIL, severity=Severity.CRITICAL,
                    actual=img.src, location=f"HTML image #{i+1}",
                    recommendation="This may be a broken/expired asset link — the response was not a valid image file.",
                    source_rule="Remote image verification",
                ))
                continue

            if img.width and img.height:
                try:
                    declared = (int(img.width), int(img.height))
                    if declared != (real_w, real_h):
                        issues.append(Issue(
                            category="Images", title="Declared HTML size doesn't match the actual image file",
                            status=Status.FAIL, severity=Severity.MEDIUM,
                            expected=f"file is {real_w}x{real_h}", actual=f"HTML declares {declared[0]}x{declared[1]}",
                            location=f"HTML image #{i+1}",
                            recommendation="The image will be stretched/squashed in clients that honor the width/height attributes.",
                            source_rule="Remote image verification",
                        ))
                except ValueError:
                    pass

            spec, filename = _find_spec(img.src, image_specs)
            budget_note = ""
            if spec and spec.get("target_size"):
                budget = _parse_size_range_kb(spec["target_size"])
                if budget:
                    lo, hi = budget
                    if not (lo <= real_kb <= hi):
                        issues.append(Issue(
                            category="Images", title="Real file size is outside the checklist's target budget",
                            status=Status.WARNING, severity=Severity.MEDIUM,
                            expected=f"{spec['target_size']} (per checklist)", actual=f"{real_kb:.0f}KB",
                            location=f"HTML image #{i+1} ({filename})",
                            recommendation="Recompress this asset to fit the client's stated file-size budget.",
                            source_rule="Image file-size budget (images（AEM）sheet)",
                        ))
                        budget_note = " — OUTSIDE TARGET BUDGET"
                    else:
                        budget_note = " — within target budget"

            issues.append(Issue(
                category="Images", title=f"Image verified ({real_w}x{real_h}, {real_kb:.0f}KB{budget_note})",
                status=Status.PASS, severity=Severity.INFO,
                location=f"HTML image #{i+1}",
                source_rule="Remote image verification",
            ))

        except Exception as e:
            issues.append(Issue(
                category="Images", title="Image could not be fetched",
                status=Status.FAIL, severity=Severity.CRITICAL,
                actual=f"{img.src} — {e}", location=f"HTML image #{i+1}",
                recommendation="Broken image link — this will show as a missing image in every email client.",
                source_rule="Remote image verification",
            ))

    if len(candidates) > max_images:
        issues.append(Issue(
            category="Images", title=f"{len(candidates) - max_images} additional image(s) not verified (limit reached)",
            status=Status.NOT_CHECKED, severity=Severity.INFO,
        ))
    if skipped:
        issues.append(Issue(
            category="Images", title=f"{skipped} image(s) skipped (relative/non-http src)",
            status=Status.INFO, severity=Severity.INFO,
        ))

    return issues
