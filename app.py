"""
FIDELITAS — Emailer QA Audit Platform
Main Streamlit application.

Run with:  streamlit run app.py
"""

import os
import tempfile
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from modules.checklist_parser import parse_checklist_workbook
from modules.html_parser import load_html_from_upload, fetch_html_from_url
from modules.pptx_parser import parse_pptx
from modules.audit import run_full_audit
from modules.scoring import compute_scores
from modules.report import issues_to_csv, build_html_report, build_pdf_report, build_excel_report
from modules.models import Status, ReferenceVariant
from modules.rules import RuleSet, list_rule_sets, load_rule_set, save_rule_set
from modules import history_store
from modules.ai_assistant import generate_summary, DEFAULT_MODEL
from modules.engines.technical_engine import build_checklist_groups

st.set_page_config(page_title="FIDELITAS — Emailer QA Auditor", page_icon="▪", layout="wide")

# ---------------------------------------------------------------- styling --
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

:root {
    --fq-bg: #0a0b0f;
    --fq-surface: #14161d;
    --fq-surface-2: #1a1d26;
    --fq-border: #262a35;
    --fq-border-soft: #1e212a;
    --fq-text: #eef0f3;
    --fq-text-muted: #8890a0;
    --fq-text-dim: #545b69;
    --fq-accent: #7c9eff;
    --fq-accent-soft: rgba(124,158,255,0.10);
    --fq-radius: 6px;
    --fq-shadow: 0 1px 3px rgba(0,0,0,0.35), 0 8px 24px rgba(0,0,0,0.22);
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
code, .fq-mono, .fq-chip { font-family: 'JetBrains Mono', 'Courier New', monospace !important; }

footer {visibility: hidden;}
.block-container {padding-top: 1.6rem; max-width: 1340px;}

[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }

.fq-hero {
    background: linear-gradient(145deg, #171a24 0%, #0e0f14 100%);
    border: 1px solid var(--fq-border); border-radius: var(--fq-radius);
    padding: 28px 34px; margin-bottom: 22px; box-shadow: var(--fq-shadow);
}
.fq-hero h1 {
    margin: 0; font-size: 25px; font-weight: 800;
    letter-spacing: 0.20em; color: var(--fq-text); font-family: 'JetBrains Mono', monospace;
}
.fq-hero .masthead-rule { border: none; border-top: 1px solid var(--fq-border); margin: 13px 0 10px 0; }
.fq-hero p {
    margin: 0; color: var(--fq-text-muted); font-size: 11px;
    letter-spacing: 0.09em; text-transform: uppercase; font-weight: 500;
}

.fq-card {
    background: var(--fq-surface); border: 1px solid var(--fq-border); border-radius: var(--fq-radius);
    padding: 20px 22px; margin-bottom: 14px; box-shadow: var(--fq-shadow);
}
.fq-label {
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.14em;
    color: var(--fq-accent); text-transform: uppercase; margin: 4px 0 12px 0;
    border-bottom: 1px solid var(--fq-border); padding-bottom: 8px;
}
.fq-chip {
    display:inline-block; padding: 3px 10px; border-radius: 3px;
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.05em;
    margin-right: 8px; color: #0a0b0f;
}
.fq-subtle { color: var(--fq-text-dim); font-size: 11px; letter-spacing: 0.03em; }
.fq-warn-banner {
    background: rgba(224,85,79,0.10); border: 1px solid rgba(224,85,79,0.35);
    border-radius: var(--fq-radius); padding: 10px 14px; font-size: 12px;
    color: #ff9d98; margin-bottom: 10px;
}

.fq-gauge-wrap { display:flex; align-items:center; gap: 22px; }
.fq-gauge {
    width: 118px; height: 118px; border-radius: 50%; flex-shrink: 0;
    background: conic-gradient(var(--fq-gauge-color) calc(var(--fq-pct) * 3.6deg), var(--fq-border-soft) 0deg);
    display:flex; align-items:center; justify-content:center;
}
.fq-gauge-inner {
    width: 92px; height: 92px; border-radius: 50%; background: var(--fq-surface);
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    border: 1px solid var(--fq-border-soft);
}
.fq-gauge-inner .val { font-size: 25px; font-weight: 800; color: var(--fq-gauge-color); font-family:'JetBrains Mono',monospace; line-height:1; }
.fq-gauge-inner .unit { font-size: 9px; color: var(--fq-text-dim); letter-spacing:0.08em; margin-top:2px; }

.score-delta {font-size:13px; font-weight:600; margin-top:2px; letter-spacing: 0.02em; font-family:'JetBrains Mono',monospace;}

div[data-testid="stMetricValue"] {font-size: 25px; font-family:'JetBrains Mono',monospace;}
div[data-testid="stMetricLabel"] {letter-spacing: 0.08em; text-transform: uppercase; font-size: 10.5px; color: var(--fq-text-muted);}

section[data-testid="stSidebar"] { background: var(--fq-surface); border-right: 1px solid var(--fq-border); }
div[data-testid="stExpander"] { border: 1px solid var(--fq-border) !important; border-radius: var(--fq-radius) !important; background: var(--fq-surface-2); }
.stButton > button, .stDownloadButton > button {
    border-radius: 4px !important; font-weight: 600 !important; letter-spacing: 0.04em !important;
    font-size: 12.5px !important; text-transform: uppercase !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="fq-hero">
  <h1>FIDELITAS</h1>
  <hr class="masthead-rule">
  <p>Emailer QA Audit Platform &nbsp;»&nbsp; Client Reference Verified Against Implementation</p>
</div>
""", unsafe_allow_html=True)


def section_label(text: str):
    st.markdown(f'<div class="fq-label">{text}</div>', unsafe_allow_html=True)


def status_chip_html(status: Status) -> str:
    return f'<span class="fq-chip" style="background:{status.color};">STATUS: {status.label}</span>'


def severity_chip_html(severity) -> str:
    return f'<span class="fq-chip" style="background:{severity.color};">[{severity.code}] {severity.value}</span>'


def render_issue_detail(issue):
    st.markdown(
        status_chip_html(issue.status) + severity_chip_html(issue.severity) +
        f'<span class="fq-chip" style="background:#2a2d35;color:#c9cdd6;">{issue.category.upper()}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("")
    cols = st.columns(2)
    if issue.expected:
        cols[0].markdown(f"**EXPECTED (REFERENCE)**\n\n{issue.expected}")
    if issue.actual:
        cols[1].markdown(f"**ACTUAL (IMPLEMENTATION)**\n\n{issue.actual}")
    if issue.difference:
        st.markdown(f"**DIFFERENCE** » {issue.difference}")
    if issue.location:
        st.caption(f"LOCATION » {issue.location}")
    if issue.recommendation:
        st.info(f"RECOMMENDATION » {issue.recommendation}")


if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "parse_warnings" not in st.session_state:
    st.session_state.parse_warnings = None


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    section_label("01 » CLIENT REFERENCE")
    checklist_file = st.file_uploader(
        "Checklist (.xlsx)", type=["xlsx"],
        help="The QA checkpoints to run — every item in this file drives what gets checked. Up to 5GB.")
    pptx_file = st.file_uploader(
        "PPTX Reference (.pptx)", type=["pptx"],
        help="The client's content/design reference — subject line, CTA copy, CTA URLs, and body copy are checked against this. Up to 5GB.")

    section_label("02 » IMPLEMENTATION")
    html_file = st.file_uploader(
        "Developer HTML / ZIP", type=["html", "htm", "zip"],
        help="The developer-built emailer HTML, or a ZIP package containing it. Up to 5GB.")

    section_label("03 » ENVIRONMENT URLS [OPTIONAL]")
    live_url = st.text_input("Live Emailer URL", placeholder="https://...")
    s3_url = st.text_input("S3 Emailer URL", placeholder="https://...")
    litmus_url = st.text_input("Litmus Emailer URL", placeholder="https://...")

    check_links = st.checkbox("Verify every link's HTTP status", value=False,
                               help="Sends real HTTP requests to every link found. Off by default to keep audits fast.")
    verify_images = st.checkbox("Verify images (fetch and inspect real files)", value=False,
                                 help="Downloads every image over HTTP to check real dimensions/file size with Pillow. Off by default — slower and uses bandwidth.")
    disable_ssl_verify = st.checkbox("Disable SSL certificate verification", value=False,
                                      help="Only enable this if you're on a corporate network whose proxy performs "
                                           "SSL inspection with a self-signed certificate (this is what causes a "
                                           "'self-signed certificate in certificate chain' error). This weakens "
                                           "the security of these specific requests — leave off unless you're "
                                           "seeing that exact error.")
    if disable_ssl_verify:
        st.markdown('<div class="fq-warn-banner">SSL certificate verification is OFF for Live/S3/Litmus '
                     'fetches and link/image checks. Only real corporate-proxy environments should need this.</div>',
                     unsafe_allow_html=True)

    section_label("04 » QA RULES [OPTIONAL]")
    with st.expander("CONFIGURE RULE SET"):
        st.caption("Unconfigured fields are skipped, never assumed.")
        existing_names = list_rule_sets()
        chosen_name = st.selectbox("Rule set", existing_names, index=existing_names.index("Generic Emailer Rules") if "Generic Emailer Rules" in existing_names else 0)
        active_rules = load_rule_set(chosen_name)

        rs_name = st.text_input("Rule set name", value=active_rules.name)
        c1, c2 = st.columns(2)
        fs_min = c1.number_input("CTA font-size min (px)", min_value=0, value=active_rules.cta_font_size_min_px or 0, help="0 = not enforced")
        fs_max = c2.number_input("CTA font-size max (px)", min_value=0, value=active_rules.cta_font_size_max_px or 0, help="0 = not enforced")
        br_min = st.number_input("CTA border-radius min (px)", min_value=0, value=active_rules.cta_border_radius_min_px or 0, help="0 = not enforced")
        bg_color = st.text_input("CTA background color (hex)", value=active_rules.cta_background_color or "", placeholder="#40000E")
        spacing_tol = st.number_input("Spacing tolerance (px)", min_value=0, value=active_rules.spacing_tolerance_px)
        case_sensitive = st.checkbox("Case-sensitive text matching", value=active_rules.case_sensitive)
        jp_strict = st.checkbox("Strict Japanese punctuation", value=active_rules.japanese_punctuation_strict)

        active_rules = RuleSet(
            name=rs_name,
            cta_font_size_min_px=fs_min or None, cta_font_size_max_px=fs_max or None,
            cta_border_radius_min_px=br_min or None, cta_background_color=(bg_color or None),
            spacing_tolerance_px=spacing_tol, case_sensitive=case_sensitive,
            japanese_punctuation_strict=jp_strict,
        )
        if st.button("COMMIT RULE SET", use_container_width=True):
            save_rule_set(active_rules)
            st.success(f"SAVED » {rs_name}")
            st.rerun()

    section_label("05 » AI ASSISTANT [OPTIONAL]")
    with st.expander("CONFIGURE AI SUMMARY"):
        st.caption("Off by default. If enabled, a summary of your already-computed findings "
                   "(not raw file contents) is sent to the Anthropic API using your own key. "
                   "Deterministic checks always run regardless — this never replaces them.")
        ai_enabled = st.checkbox("Enable AI-generated executive summary", value=False)
        ai_api_key = st.text_input("Your Anthropic API key", type="password") if ai_enabled else ""
        ai_model = st.selectbox("Model", ["claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-opus-4-8"]) if ai_enabled else DEFAULT_MODEL

    st.markdown('<hr style="border-color:#262a35;">', unsafe_allow_html=True)
    run_disabled = not (html_file and (checklist_file or pptx_file))
    run_clicked = st.button("EXECUTE AUDIT", type="primary", use_container_width=True, disabled=run_disabled)
    if run_disabled:
        st.caption("Upload the developer HTML and at least one client reference (checklist and/or PPTX) to begin.")


# ------------------------------------------------------------- parse & run
if run_clicked:
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, html_file.name)
        with open(html_path, "wb") as f:
            f.write(html_file.getbuffer())

        with st.status("EXECUTING AUDIT SEQUENCE...", expanded=True) as status_box:
            all_warnings = []
            checklist_model = None
            pptx_ref_variant = None

            if checklist_file:
                st.write("PARSING » client checklist workbook")
                checklist_path = os.path.join(tmp, checklist_file.name)
                with open(checklist_path, "wb") as f:
                    f.write(checklist_file.getbuffer())
                checklist_model, warnings = parse_checklist_workbook(checklist_path)
                all_warnings += [(w.sheet, w.message) for w in warnings]

            if pptx_file:
                st.write("PARSING » client PPTX reference")
                pptx_path = os.path.join(tmp, pptx_file.name)
                with open(pptx_path, "wb") as f:
                    f.write(pptx_file.getbuffer())
                pptx_model, pptx_warnings = parse_pptx(pptx_path)
                all_warnings += [("PPTX", w) for w in pptx_warnings]
                if pptx_model.variants:
                    pptx_ref_variant = pptx_model.variants[0]

            st.session_state.parse_warnings = all_warnings

            st.write("PARSING » developer HTML")
            html_impl = load_html_from_upload(html_path, "Developer HTML")

            other_sources = []
            for label, url in [("Live URL", live_url), ("S3 URL", s3_url), ("Litmus URL", litmus_url)]:
                if url.strip():
                    st.write(f"FETCHING » {label}")
                    other_sources.append(fetch_html_from_url(url.strip(), label, verify_ssl=not disable_ssl_verify))

            if checklist_model and checklist_model.variants:
                primary_variants = checklist_model.variants
                project_name = checklist_model.project_name
                checklist_items = checklist_model.checklist_items
                image_specs = checklist_model.image_specs
                image_size_legend = checklist_model.image_size_legend
            elif pptx_ref_variant or (checklist_model and checklist_model.checklist_items):
                # No positional DEM/SC content variant exists — either the
                # checklist file has no such sheets (a flat checklist-only
                # workbook), or none was uploaded at all. That does NOT mean
                # there's nothing to audit: the checklist's own checkpoints
                # (border/width/mirror-tag/footer/ALT/links/CTA/multi-source
                # consistency, etc.) all run against the HTML directly and
                # don't require positional reference blocks. A single
                # placeholder variant is used so the audit actually runs
                # instead of silently discarding every checklist item.
                primary_variants = [ReferenceVariant(name="PPTX Reference Audit" if pptx_ref_variant else "Checklist Audit")]
                project_name = checklist_model.project_name if checklist_model else None
                checklist_items = checklist_model.checklist_items if checklist_model else []
                image_specs = checklist_model.image_specs if checklist_model else []
                image_size_legend = checklist_model.image_size_legend if checklist_model else {}
            else:
                primary_variants = []
                project_name = None
                checklist_items = []
                image_specs = []
                image_size_legend = {}

            if not primary_variants:
                status_box.update(label="AUDIT FAILED — NO REFERENCE CONTENT FOUND", state="error")
                st.error("[ERR] Could not extract any reference content from the uploaded checklist/PPTX. "
                          "For the checklist, check it follows the expected DEM(n)/SC(n) sheet layout.")
            else:
                results_by_variant = {}
                for variant in primary_variants:
                    st.write(f"AUDITING » {variant.name}")
                    prev_score = history_store.get_last_score(project_name, variant.name)

                    issues = run_full_audit(
                        variant, html_impl, other_sources, checklist_items,
                        check_links=check_links, verify_images=verify_images,
                        ruleset=active_rules, pptx_variant=pptx_ref_variant,
                        image_specs=image_specs, image_size_legend=image_size_legend,
                        verify_ssl=not disable_ssl_verify,
                    )
                    scores = compute_scores(issues)
                    history_store.record_run(project_name, variant.name, scores["overall"], scores["counts"], scores["total_checks"])

                    raw_automated = [i for i in issues if i.category != "Checklist Item"]
                    checklist_groups = build_checklist_groups(checklist_items, raw_automated) if checklist_items else []

                    results_by_variant[variant.name] = {
                        "issues": issues, "scores": scores, "prev_score": prev_score,
                        "checklist_groups": checklist_groups,
                    }

                parse_summary_rows = []
                for variant in primary_variants:
                    kind_counts = {}
                    for b in variant.blocks:
                        kind_counts[b.kind] = kind_counts.get(b.kind, 0) + 1
                    kind_str = " · ".join(f"{k.upper()}: {v}" for k, v in sorted(kind_counts.items())) or "NO BLOCKS PARSED"
                    parse_summary_rows.append({"SHEET": variant.name, "TOTAL BLOCKS": len(variant.blocks), "BREAKDOWN": kind_str})
                if pptx_ref_variant:
                    kind_counts = {}
                    for b in pptx_ref_variant.blocks:
                        kind_counts[b.kind] = kind_counts.get(b.kind, 0) + 1
                    kind_str = " · ".join(f"{k.replace('pptx_','').upper()}: {v}" for k, v in sorted(kind_counts.items())) or "NO BLOCKS PARSED"
                    parse_summary_rows.append({"SHEET": "PPTX (all slides)", "TOTAL BLOCKS": len(pptx_ref_variant.blocks), "BREAKDOWN": kind_str})

                st.session_state.audit_results = {
                    "by_variant": results_by_variant,
                    "html_impl": html_impl,
                    "other_sources": other_sources,
                    "project_name": project_name,
                    "parse_summary_rows": parse_summary_rows,
                    "image_spec_count": len(image_specs),
                    "image_legend": image_size_legend,
                    "checklist_item_count": len(checklist_items),
                }
                status_box.update(label="AUDIT COMPLETE", state="complete")
                st.toast(f"AUDIT COMPLETE — {sum(r['scores']['total_checks'] for r in results_by_variant.values())} CHECKS EXECUTED")


# ---------------------------------------------------------------- warnings
if st.session_state.parse_warnings:
    with st.expander(f"[ADVISORY] {len(st.session_state.parse_warnings)} PARSING NOTE(S) — DATA NOT FULLY READABLE FROM SOURCE FILE(S)", expanded=False):
        for sheet, msg in st.session_state.parse_warnings:
            st.markdown(f"- **{sheet}** » {msg}")


# ------------------------------------------------------------------ report
results = st.session_state.audit_results
if results:
    with st.expander("PARSED REFERENCE CONTENT — VERIFY AGAINST YOUR SOURCE FILE(S)", expanded=False):
        st.caption("Every sheet FIDELITAS found and interpreted as source-of-truth content, and exactly "
                   "how many blocks of each kind it extracted from each. Cross-check this against your "
                   "checklist directly — if a sheet you expected is missing here, it was not recognized.")
        st.dataframe(pd.DataFrame(results["parse_summary_rows"]), use_container_width=True, hide_index=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("IMAGE SPEC ROWS", results["image_spec_count"])
        m2.metric("SIZE-CODE LEGEND ENTRIES", len(results["image_legend"]))
        m3.metric("CHECKLIST SIGN-OFF ITEMS", results["checklist_item_count"])
        if results["image_legend"]:
            st.caption("SIZE CODE » DIMENSION LEGEND (from the 'Image size' sheet):")
            st.dataframe(
                pd.DataFrame([{"CODE": k.upper(), "DIMENSIONS": v} for k, v in results["image_legend"].items()]),
                use_container_width=True, hide_index=True,
            )

    with st.expander("EMAILER PREVIEW", expanded=True):
        preview_tabs_data = [("Developer HTML", results["html_impl"])]
        for src in results["other_sources"]:
            if not src.fetch_error:
                preview_tabs_data.append((src.source_name, src))
        tabs = st.tabs([t[0] for t in preview_tabs_data])
        for tab, (label, src) in zip(tabs, preview_tabs_data):
            with tab:
                if src.raw_html:
                    components.html(src.raw_html, height=650, scrolling=True)
                else:
                    st.caption("No renderable HTML available for this source.")
        skipped_previews = [s.source_name for s in results["other_sources"] if s.fetch_error]
        if skipped_previews:
            st.caption(f"Not shown (could not be fetched): {', '.join(skipped_previews)} — see the warning above for why.")

    variant_names = list(results["by_variant"].keys())
    selected_variant = st.selectbox("VIEWING RESULTS » VARIANT", variant_names)
    data = results["by_variant"][selected_variant]
    issues = data["issues"]
    scores = data["scores"]
    prev_score = data["prev_score"]
    checklist_groups = data["checklist_groups"]

    if any(s.fetch_error for s in results["other_sources"]):
        for s in results["other_sources"]:
            if s.fetch_error:
                st.warning(f"[NOT VERIFIED] {s.source_name} — {s.fetch_error}")

    # ---- dashboard ----
    col1, col2 = st.columns([1, 2.2])
    with col1:
        st.markdown('<div class="fq-card">', unsafe_allow_html=True)
        overall = scores["overall"]
        pct = overall if overall is not None else 0
        color = "#3ecf7e" if pct >= 90 else "#e0b433" if pct >= 75 else "#e0554f"
        display_val = f"{overall}" if overall is not None else "N/A"
        st.markdown(f'''
            <div class="fq-gauge-wrap">
              <div class="fq-gauge" style="--fq-pct:{pct}; --fq-gauge-color:{color};">
                <div class="fq-gauge-inner">
                  <div class="val">{display_val}</div>
                  <div class="unit">{"PERCENT" if overall is not None else "SCORE"}</div>
                </div>
              </div>
              <div>
                <div class="fq-label" style="margin:0 0 6px 0; border:none; padding:0;">OVERALL QA SCORE</div>
                <div class="fq-subtle">EXCLUDES MANUAL-REVIEW AND NOT-CHECKED ITEMS</div>
              </div>
            </div>
        ''', unsafe_allow_html=True)
        if prev_score is not None and overall is not None:
            delta = round(overall - prev_score, 1)
            d_color = "#3ecf7e" if delta >= 0 else "#e0554f"
            d_mark = "▲" if delta >= 0 else "▼"
            st.markdown(f'<div class="score-delta" style="color:{d_color};margin-top:14px;">{d_mark} {"+" if delta>=0 else ""}{delta}% VS LAST AUDIT ({prev_score}%)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        counts = scores["counts"]
        c1, c2 = st.columns(2)
        c1.metric(Status.PASS.label, counts.get(Status.PASS, 0))
        c1.metric(Status.FAIL.label, counts.get(Status.FAIL, 0))
        c2.metric(Status.WARNING.label, counts.get(Status.WARNING, 0))
        c2.metric(Status.MANUAL_REVIEW.label, counts.get(Status.MANUAL_REVIEW, 0))
        st.caption(f"{Status.NOT_CHECKED.label}: {counts.get(Status.NOT_CHECKED, 0)}  »  TOTAL CHECKS: {scores['total_checks']}")

    with col2:
        st.markdown('<div class="fq-card">', unsafe_allow_html=True)
        st.markdown('<div class="fq-label" style="margin-top:0;">CATEGORY SCORES</div>', unsafe_allow_html=True)
        chart_rows = {cat: sc for cat, sc in scores["by_category"].items() if sc is not None}
        if chart_rows:
            st.bar_chart(pd.DataFrame({"Score": chart_rows}), height=200)
        for cat, sc in sorted(scores["by_category"].items(), key=lambda x: (x[1] is None, x[0])):
            if sc is None:
                st.markdown(f"`{cat}` — MANUAL REVIEW ONLY")
        st.markdown('</div>', unsafe_allow_html=True)

    if ai_enabled:
        st.markdown('<div class="fq-card">', unsafe_allow_html=True)
        st.markdown('<div class="fq-label" style="margin-top:0;">AI EXECUTIVE SUMMARY — EXTERNAL API CALL</div>', unsafe_allow_html=True)
        if st.button("GENERATE SUMMARY"):
            if not ai_api_key:
                st.warning("[ERR] Enter your Anthropic API key in the sidebar first.")
            else:
                with st.spinner("SUMMARIZING FINDINGS..."):
                    text, err = generate_summary(ai_api_key, results["project_name"], selected_variant, scores, issues, model=ai_model)
                if err:
                    st.error(f"[ERR] Could not generate summary — {err}")
                elif text:
                    st.markdown(text)
        st.markdown('</div>', unsafe_allow_html=True)

    hist = history_store.get_history(results["project_name"], selected_variant)
    if len(hist) > 1:
        with st.expander(f"AUDIT HISTORY — {len(hist)} RUN(S) ON RECORD"):
            hist_df = pd.DataFrame(hist)
            hist_df["overall_score"] = pd.to_numeric(hist_df["overall_score"], errors="coerce")
            st.line_chart(hist_df.set_index("timestamp")["overall_score"])
            st.dataframe(hist_df[["timestamp", "overall_score", "total_checks"]], use_container_width=True, hide_index=True)

    # ---------------------------------------------------------- findings --
    section_label("AUDIT FINDINGS")

    if checklist_groups:
        tab_checklist, tab_all = st.tabs(["BY CHECKLIST ITEM", "ALL FINDINGS (DETAILED)"])
    else:
        tab_checklist, tab_all = None, st.container()
        st.caption("No checklist items were parsed from the uploaded file(s) — showing all findings directly.")

    if tab_checklist is not None:
        with tab_checklist:
            st.caption("Every checkpoint from your checklist, in order, with the specific evidence "
                       "that produced its status nested underneath. This is the primary view — "
                       "engine-level detail is here as supporting evidence, not a separate parallel list.")
            cg_status_filter = st.multiselect(
                "STATUS", [s.label for s in Status],
                default=[Status.FAIL.label, Status.WARNING.label, Status.MANUAL_REVIEW.label],
                key="cg_status_filter",
            )
            filtered_groups = [g for g in checklist_groups if not cg_status_filter or g["status"].label in cg_status_filter]
            st.caption(f"SHOWING {len(filtered_groups)} OF {len(checklist_groups)} CHECKLIST ITEMS")

            for g in filtered_groups:
                item, status, supporting, reason = g["item"], g["status"], g["supporting"], g["reason"]
                header = f"STATUS: {status.label}   [#{item.number}]   »   {item.text_en.splitlines()[0][:90]}"
                with st.expander(header):
                    st.markdown(status_chip_html(status), unsafe_allow_html=True)
                    st.markdown("")
                    st.markdown(f"**CHECKLIST TEXT**\n\n{item.text_en}")
                    if item.text_ja:
                        st.caption(item.text_ja)
                    if item.dev_status:
                        st.caption(f"DEV STATUS (from checklist) » {item.dev_status}")
                    st.caption(f"SOURCE » {item.source_sheet}")
                    if reason:
                        st.info(f"NOTE » {reason}")
                    if supporting:
                        st.markdown(f"**SUPPORTING EVIDENCE ({len(supporting)})**")
                        for s_issue in supporting:
                            with st.container(border=True):
                                render_issue_detail(s_issue)

    with (tab_all if tab_checklist is None else tab_all):
        fcol1, fcol2, fcol3, fcol4 = st.columns([1.1, 1, 1.1, 1.8])
        status_filter = fcol1.multiselect(
            "STATUS", [s.label for s in Status],
            default=[Status.FAIL.label, Status.WARNING.label], key="all_status_filter")
        sev_options = sorted(set(i.severity.value for i in issues), key=lambda v: ["CRITICAL","HIGH","MEDIUM","LOW","INFO"].index(v))
        sev_filter = fcol2.multiselect("SEVERITY", sev_options, default=[], key="all_sev_filter")
        cat_options = sorted(set(i.category for i in issues))
        cat_filter = fcol3.multiselect("CATEGORY", cat_options, default=[], key="all_cat_filter")
        search = fcol4.text_input("SEARCH FINDINGS", placeholder="e.g. CTA, ALT, spacing...", key="all_search")

        filtered = issues
        if status_filter:
            filtered = [i for i in filtered if i.status.label in status_filter]
        if sev_filter:
            filtered = [i for i in filtered if i.severity.value in sev_filter]
        if cat_filter:
            filtered = [i for i in filtered if i.category in cat_filter]
        if search:
            s = search.lower()
            filtered = [i for i in filtered if s in (i.title + str(i.expected) + str(i.actual) + str(i.difference)).lower()]

        st.caption(f"SHOWING {len(filtered)} OF {len(issues)} TOTAL FINDINGS")

        workflow_options = ["Open", "In Progress", "Fixed", "Recheck", "Passed"]
        for issue in filtered:
            header = f"STATUS: {issue.status.label}   [{issue.severity.code}]   »   {issue.title}"
            with st.expander(header):
                render_issue_detail(issue)
                if issue.source_rule:
                    st.caption(f"REFERENCE » {issue.source_rule}")
                wf_key = f"wf::{selected_variant}::{abs(hash((issue.category, issue.title, issue.location)))}"
                default_idx = workflow_options.index(issue.workflow_status) if issue.workflow_status in workflow_options else 0
                chosen_wf = st.selectbox("WORKFLOW STATUS", workflow_options, index=default_idx, key=wf_key)
                issue.workflow_status = chosen_wf

    section_label("REPORT EXPORT")
    ecol1, ecol2, ecol3, ecol4 = st.columns(4)
    csv_bytes = issues_to_csv(issues)
    html_report = build_html_report(results["project_name"] or "Unknown Project", selected_variant, scores, issues, checklist_groups)
    pdf_bytes = build_pdf_report(results["project_name"] or "Unknown Project", selected_variant, scores, issues, checklist_groups)
    xlsx_bytes = build_excel_report(results["project_name"] or "Unknown Project", selected_variant, scores, issues, checklist_groups)
    ecol1.download_button("EXPORT — CSV", data=csv_bytes, file_name=f"fidelitas_audit_{selected_variant}.csv",
                           mime="text/csv", use_container_width=True)
    ecol2.download_button("EXPORT — HTML", data=html_report.encode("utf-8"),
                           file_name=f"fidelitas_audit_{selected_variant}.html", mime="text/html",
                           use_container_width=True)
    ecol3.download_button("EXPORT — PDF", data=pdf_bytes, file_name=f"fidelitas_audit_{selected_variant}.pdf",
                           mime="application/pdf", use_container_width=True)
    ecol4.download_button("EXPORT — XLSX", data=xlsx_bytes, file_name=f"fidelitas_audit_{selected_variant}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

else:
    st.markdown("""
    <div class="fq-card">
    <div class="fq-label" style="margin-top:0;">SYSTEM OVERVIEW</div>
    01 » Upload the client checklist workbook and/or a client PPTX reference deck.<br>
    02 » Upload the developer HTML or a ZIP package containing it.<br>
    03 » Optionally provide Live / S3 / Litmus URLs for cross-environment consistency checks.<br>
    04 » Optionally configure QA Rules (CTA styling) and/or enable the AI summary.<br>
    05 » Select EXECUTE AUDIT.<br><br>
    FIDELITAS treats your checklist's own checkpoints as the primary structure of the audit —
    findings are organized by checklist item first, with the underlying evidence nested
    underneath, rather than as one long undifferentiated list. PPTX slide content (subject line,
    CTA copy, CTA URLs, body text) is checked against the implementation as real content QA, not
    just a formality. Anything that cannot be genuinely verified (Litmus rendering, PSD-vs-HTML
    aspect ratio, dark mode, etc.) is explicitly marked Manual Review — never a fabricated pass.
    Files up to 5GB are supported.
    </div>
    """, unsafe_allow_html=True)
