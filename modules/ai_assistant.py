"""
FIDELITAS — Optional AI Assistant

Per the original spec: AI may help explain/summarize findings, but must
NEVER be the QA mechanism itself — every finding it discusses was already
produced by a deterministic engine above. This module only runs if the
user explicitly opts in and supplies their own Anthropic API key (this is
a standalone local app, not running inside claude.ai, so there is no
ambient API access — nothing is sent anywhere unless the user turns this
on and provides a key).
"""

import json
import requests

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"


def generate_summary(api_key: str, project_name: str, variant: str, scores: dict,
                      issues: list, model: str = DEFAULT_MODEL, max_issues: int = 30):
    """Returns (summary_text_or_None, error_message_or_None). Never raises."""
    if not api_key or not api_key.strip():
        return None, "No API key provided."

    priority_issues = [i for i in issues if i.status.value in ("FAIL", "WARNING")][:max_issues]
    lines = [
        f"Project: {project_name or 'Unknown'}",
        f"Variant: {variant}",
        f"Overall QA score: {scores.get('overall')}",
        f"Category scores: {json.dumps(scores.get('by_category', {}), ensure_ascii=False)}",
        f"Counts: {json.dumps({k.value: v for k, v in scores.get('counts', {}).items()}, ensure_ascii=False)}",
        "",
        f"Top {len(priority_issues)} failed/warning findings (already verified by deterministic checks — do not invent new ones):",
    ]
    for i in priority_issues:
        lines.append(
            f"- [{i.severity.value}] {i.category} | {i.title} | expected={i.expected!r} actual={i.actual!r} diff={i.difference!r}"
        )

    prompt = (
        "You are assisting a QA engineer reviewing an automated emailer audit. "
        "Below is the real, already-computed audit data. Write a concise executive "
        "summary (plain text, no markdown headers): 1) overall verdict, 2) the 3-5 "
        "most important issues to fix first and why, 3) any pattern you notice across "
        "issues. Do not claim to have checked anything yourself — you are only "
        "summarizing the findings given to you.\n\n" + "\n".join(lines)
    )

    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": api_key.strip(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 700,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        return None, f"Network error calling Anthropic API: {e}"

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            detail = resp.text[:200]
        return None, f"Anthropic API returned HTTP {resp.status_code}: {detail}"

    try:
        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return (text.strip() or None), None if text.strip() else "API returned an empty response."
    except Exception as e:
        return None, f"Could not parse API response: {e}"
