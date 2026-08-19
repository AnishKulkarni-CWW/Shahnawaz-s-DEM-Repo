"""
FIDELITAS — Link Status Engine

Actually requests every link found in the HTML and reports its real HTTP
status. Never fabricates a status code — if a request errors out (timeout,
DNS failure, connection refused, blocked by the target site), that is
reported as NOT_VERIFIED with the real reason, not silently marked as pass.
"""

import requests
from ..models import Issue, Status, Severity, ImplementationModel

TIMEOUT = 8


def check_links(impl: ImplementationModel, max_links: int = 40, verify_ssl: bool = True) -> list:
    issues = []
    links = [l for l in impl.links if l.href and l.href.startswith("http")]
    skipped = len(impl.links) - len(links)

    for link in links[:max_links]:
        try:
            resp = requests.head(
                link.href, timeout=TIMEOUT, allow_redirects=True, verify=verify_ssl,
                headers={"User-Agent": "Mozilla/5.0 (FIDELITAS QA Auditor)"},
            )
            if resp.status_code == 405:  # some servers reject HEAD
                resp = requests.get(link.href, timeout=TIMEOUT, allow_redirects=True, verify=verify_ssl,
                                     headers={"User-Agent": "Mozilla/5.0 (FIDELITAS QA Auditor)"})

            final_url = resp.url
            redirect_note = f" (redirected to {final_url})" if final_url != link.href else ""

            if resp.status_code < 400:
                issues.append(Issue(
                    category="Links", title=f"Link returns HTTP {resp.status_code}",
                    status=Status.PASS, severity=Severity.INFO,
                    actual=f"{link.href}{redirect_note} -> {resp.status_code}",
                    location=f"'{link.text[:40]}'" if link.text else link.href,
                    source_rule="Link/CTA reachability",
                ))
            else:
                issues.append(Issue(
                    category="Links", title=f"Link returns HTTP {resp.status_code}",
                    status=Status.FAIL, severity=Severity.CRITICAL,
                    actual=f"{link.href}{redirect_note} -> {resp.status_code}",
                    location=f"'{link.text[:40]}'" if link.text else link.href,
                    recommendation="Fix or replace this broken link before delivery.",
                    source_rule="Link/CTA reachability",
                ))
        except requests.exceptions.RequestException as e:
            issues.append(Issue(
                category="Links", title="Link could not be verified",
                status=Status.INFO, severity=Severity.LOW,
                actual=link.href,
                location=f"'{link.text[:40]}'" if link.text else link.href,
                recommendation=f"Automated check failed ({type(e).__name__}) — verify this link manually in a browser.",
                source_rule="Link/CTA reachability",
            ))

    if len(links) > max_links:
        issues.append(Issue(
            category="Links", title=f"{len(links) - max_links} additional link(s) not checked (limit reached)",
            status=Status.NOT_CHECKED, severity=Severity.INFO,
        ))
    if skipped:
        issues.append(Issue(
            category="Links", title=f"{skipped} link(s) skipped (mailto:, anchor, or empty href)",
            status=Status.INFO, severity=Severity.INFO,
        ))

    return issues
