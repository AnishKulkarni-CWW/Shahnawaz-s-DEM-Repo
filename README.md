# FIDELITAS — Emailer QA Audit Platform

Compares a client-provided reference (checklist workbook and/or PPTX deck)
against a developer-built HTML emailer, and optionally against Live / S3 /
Litmus URLs — and tells you exactly what matches, what doesn't, and what it
genuinely can't verify from HTML alone.

## Install & run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).
Uploads support files up to **5GB**.

## Using it

1. **Upload the client checklist** (`.xlsx`) and/or a **client PPTX reference**
   (`.pptx`) — at least one is required. The checklist gives precise,
   positional ALT/CTA/title matching; the PPTX gives a looser presence check
   (see "PPTX vs. checklist" below).
2. **Upload the developer HTML** — a single `.html` file or a `.zip`
   containing one (FIDELITAS finds `index.html` automatically).
3. *(Optional)* paste **Live / S3 / Litmus URLs**, configure **QA Rules**
   (CTA font-size/border-radius/background-color), and/or enable the
   **AI Assistant** (needs your own Anthropic API key — off by default,
   nothing is sent anywhere unless you turn it on).
4. Select **EXECUTE AUDIT**.

You get a scored dashboard with category breakdown chart, audit history/
re-audit delta, a filterable/searchable issue list with expected-vs-actual
and a plain-English difference for every mismatch, per-issue workflow
tracking (Open → In Progress → Fixed → Recheck → Passed), and CSV/HTML/
PDF/Excel export.

## PPTX vs. checklist — an important distinction

The checklist workbook uses explicit `▼ALT：`/`▼CTA`/`▼URL` markers that map
each reference block to a specific position, so FIDELITAS can say "image #4
in your HTML doesn't match reference block #4." A PPTX deck has no such
convention — it's a design deck, not a marked-up spec. So PPTX checks are a
**presence check**: does this slide's text appear anywhere in the
implementation? A "not found" result there is marked [MANUAL REVIEW], not
[FAIL], because it's a weaker signal than the checklist's positional match.

## What is — and isn't — genuinely automated

| Check | How |
|---|---|
| Subject/ALT/CTA text vs. checklist reference | [VERIFIED] Positional comparison, Japanese-aware (spacing, brackets, punctuation, full/half-width, capitalization, numbers/dates/prices) |
| PPTX slide text vs. implementation | [VERIFIED] Presence-based comparison (see above) |
| `border="0"`, empty/broken ALT, 600px width, forbidden CSS, AWS host, mirror-page tag, footer presence, DOCTYPE, charset, duplicate IDs, external stylesheets | [VERIFIED] Real HTML/DOM inspection |
| Tag-balance | [ADVISORY] Best-effort heuristic, explicitly labeled as such — not a full W3C validator |
| Image dimensions vs. client spec sheet | [VERIFIED] Real comparison, using the `images（AEM）` sheet already parsed from the checklist |
| Image file integrity (real fetch, real pixel size, real file size) | [VERIFIED] Opt-in — makes real HTTP requests |
| Link HTTP status, empty/placeholder hrefs | [VERIFIED] Real checks (HTTP status is opt-in for speed; empty-href scanning always runs) |
| CTA styling vs. configurable rule set | [VERIFIED] Real inline-style parsing, only for rules you've actually configured |
| Live/S3/Litmus content consistency | [VERIFIED] Real fetch + comparison, when the URL is reachable |
| Responsive QA | [ADVISORY] Viewport-meta/`@media` **presence** only — a real signal, not a real render |
| Litmus rendering, dark mode, PSD-vs-HTML aspect ratio, email-client-specific rendering, pixel-level visual diff, screenshot evidence capture | [MANUAL REVIEW] Explicitly marked / documented as roadmap — these need real browser/email-client rendering or the original design file, which this tool does not fabricate |
| AI executive summary | [VERIFIED] Real, opt-in, uses your own API key — summarizes already-computed findings, never itself a QA mechanism |
| Checklist items with no matching engine yet | [NOT CHECKED] Explicitly marked, never assumed to pass |

Manual-review and not-checked items are excluded from the QA score entirely
— they're neither a pass nor a fail.

## QA Rules Engine

Configure CTA font-size range, minimum border-radius, and required
background color from the sidebar — no code changes needed. Rule sets are
named and saved as JSON under `qa_rules/`, so you can keep e.g. "BMW Emailer
Rules" alongside "Generic Emailer Rules". Any field left blank is treated as
"not configured" and skipped — never assumed.

## History & re-audit

Every completed audit is appended to `fidelitas_data/history.jsonl` (local
file, nothing external). When you re-run an audit for the same project +
variant, the dashboard shows the score delta against your last run
automatically, and a trend chart is available once you have more than one
run on record.

## Architecture

```
app.py                        Streamlit UI / orchestration
modules/
  models.py                   Shared dataclasses (Issue, ReferenceModel, ...)
  checklist_parser.py         Reads the client checklist workbook
  pptx_parser.py               Reads a client PPTX reference deck
  html_parser.py               Reads developer HTML/ZIP + fetches live URLs
  audit.py                     Wires all engines together for one run
  scoring.py                   Category + overall QA score
  report.py                    CSV / HTML / PDF / Excel report export
  rules.py                     QA Rules — named, saved, configurable rule sets
  history_store.py             Local audit history (JSONL) + re-audit delta
  ai_assistant.py               Optional AI summary via the user's own API key
  engines/
    text_diff.py                Japanese-aware string comparison utilities
    pattern_engine.py           Numbers/dates/prices, capitalization, full/half-width
    content_engine.py           Mail title + ALT text vs. checklist reference
    cta_engine.py                 CTA text + URL vs. checklist reference
    pptx_engine.py                Slide text presence vs. implementation
    technical_engine.py           Dev-checklist rule reconciliation
    html_lint_engine.py           DOCTYPE/charset/dup-IDs/tag-balance/external-CSS/responsive proxies/broken links
    image_engine.py               Spec-sheet dimension match + opt-in real fetch verification
    rules_engine.py                Configurable CTA styling validation
    link_engine.py                  Real HTTP status checks
    multisource_engine.py          HTML vs Live/S3/Litmus consistency
```

Adding a new check = adding a function to an existing engine (or a new file
under `modules/engines/`) and calling it from `modules/audit.py`. Nothing
else needs to change.

## Still roadmap (named honestly, not built)

- Real visual/pixel diffing against a rendered PPTX or HTML screenshot
- Real email-client rendering (Litmus API key or a headless-browser farm —
  out of scope for a local tool without those credentials)
- Screenshot evidence capture (would need Playwright + browser binaries;
  can be added as an optional dependency, gracefully degrading if absent)
- A full W3C-grade HTML validator (current tag-balance check is a heuristic)
