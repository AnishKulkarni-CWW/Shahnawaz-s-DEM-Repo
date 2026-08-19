"""
FIDELITAS — Audit Orchestrator

Runs every engine against the parsed inputs for a single DEM/SC variant and
returns the combined issue list. This is the only place that needs to
change when a new module is added to /modules/engines.
"""

from .models import ReferenceVariant, ImplementationModel
from .engines import (
    content_engine, cta_engine, technical_engine, multisource_engine,
    image_engine, html_lint_engine, rules_engine, pptx_engine,
)


def run_full_audit(variant: ReferenceVariant, html_impl: ImplementationModel,
                    other_sources: list, all_checklist_items: list,
                    check_links: bool = False, verify_images: bool = False,
                    ruleset=None, pptx_variant: ReferenceVariant = None,
                    image_specs: list = None, image_size_legend: dict = None,
                    verify_ssl: bool = True) -> list:
    issues = []

    # Content checks run against EVERY successfully-fetched environment, not
    # just the uploaded HTML — "is ALT set correctly", "is each CTA set
    # correctly", "is the subject set correctly" are checklist checkpoints
    # about the actual delivered mail, and Live/S3/Litmus are each a real,
    # independent copy of it that can drift from the developer HTML. A
    # source that failed to fetch is skipped here (already reported by
    # multisource_engine below) rather than silently treated as a pass.
    reachable_sources = [("Developer HTML", html_impl)] + [
        (s.source_name, s) for s in other_sources if not s.fetch_error
    ]
    for label, impl in reachable_sources:
        tag = "" if label == "Developer HTML" else f"[{label}] "
        for issue in content_engine.check_mail_title(variant, impl):
            issue.location = tag + (issue.location or "")
            issues.append(issue)
        for issue in content_engine.check_alt_texts(variant, impl):
            issue.location = tag + (issue.location or "")
            issues.append(issue)
        for issue in cta_engine.check_ctas(variant, impl):
            issue.location = tag + (issue.location or "")
            issues.append(issue)
        if pptx_variant is not None:
            for issue in content_engine.check_mail_title(pptx_variant, impl):
                issue.location = tag + (issue.location or "")
                issues.append(issue)
            for issue in pptx_engine.check_pptx_presence(pptx_variant, impl):
                issue.location = tag + (issue.location or "")
                issues.append(issue)
            for issue in pptx_engine.check_pptx_cta_elements(pptx_variant, impl):
                issue.location = tag + (issue.location or "")
                issues.append(issue)

    issues += content_engine.check_dynamic_block_references(variant)
    issues += technical_engine.run_html_structure_checks(html_impl)
    issues += html_lint_engine.run_lint(html_impl)
    issues += image_engine.check_image_specs(html_impl, image_specs or [], image_size_legend or {})

    if ruleset is not None:
        issues += rules_engine.check_cta_rules(html_impl, ruleset)

    if pptx_variant is not None:
        issues += pptx_engine.check_pptx_reference_metadata(pptx_variant)

    if other_sources:
        issues += multisource_engine.compare_sources(html_impl, other_sources)

    if check_links:
        from .engines import link_engine
        issues += link_engine.check_links(html_impl, verify_ssl=verify_ssl)

    if verify_images:
        issues += image_engine.verify_remote_images(html_impl, image_specs or [], verify_ssl=verify_ssl)

    issues += technical_engine.reconcile_checklist_items(all_checklist_items, issues)

    return issues
