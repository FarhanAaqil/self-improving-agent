"""Verification certificates: a portable, optionally signed record of what was verified and how.

Anyone holding the certificate can check the code they received against `code_sha256`,
see the exact sandbox configuration, and (with the server's key) verify the signature.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from html import escape

from app.config import CERT_SIGNING_KEY, SANDBOX_TIMEOUT
from app.sandbox import SANDBOX_IMAGE, docker_run_args

CERT_VERSION = 1


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def sign(payload: dict) -> str | None:
    if not CERT_SIGNING_KEY:
        return None
    return hmac.new(CERT_SIGNING_KEY.encode(), _canonical(payload), hashlib.sha256).hexdigest()


def verify_signature(certificate: dict) -> bool:
    """True when the certificate was signed by this server and hasn't been altered."""
    claimed = certificate.get("signature")
    body = {k: v for k, v in certificate.items() if k not in ("signature", "signed")}
    expected = sign(body)
    return bool(claimed and expected and hmac.compare_digest(claimed, expected))


def build_certificate(run: dict) -> dict | None:
    """Certificate for a verified run, or None when the run never passed."""
    passing = next((a for a in run.get("attempts", []) if a.get("success")), None)
    if run.get("final_status") != "success" or passing is None:
        return None

    final_code = run.get("final_code") or passing["generated_code"]
    quality = {}
    if passing.get("quality_report_json"):
        try:
            quality = json.loads(passing["quality_report_json"])
        except ValueError:
            quality = {}

    body = {
        "certificate_version": CERT_VERSION,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run["run_id"],
        "task": run["task_description"],
        "model": run.get("model_name"),
        "verified_on_attempt": passing["attempt_number"],
        "attempts": run.get("total_attempts"),
        "code_sha256": hashlib.sha256(final_code.encode()).hexdigest(),
        "verified_code_sha256": hashlib.sha256(passing["generated_code"].encode()).hexdigest(),
        "docs_applied_and_reverified": bool(run.get("docs_applied")),
        "spec_tests_sha256": hashlib.sha256((run.get("spec_tests") or "").encode()).hexdigest(),
        "tests": {"passed": passing.get("tests_passed"), "total": passing.get("tests_total")},
        "coverage": passing.get("coverage"),
        "quality_score": passing.get("quality_overall_score"),
        "bandit_issues": len(quality.get("bandit_issues", [])),
        "mutation": {
            k: (quality.get("mutation") or {}).get(k) for k in ("score", "killed", "total")
        },
        "sandbox": {
            "sandboxed": bool(passing.get("sandboxed")),
            "image": SANDBOX_IMAGE,
            "timeout_seconds": SANDBOX_TIMEOUT,
            "docker_args": docker_run_args("sandbox-<id>"),
        },
    }
    signature = sign(body)
    return {**body, "signature": signature, "signed": signature is not None}


def badge_svg(status: str, detail: str) -> str:
    """Small square badge in the ledger palette (verified = green, otherwise red)."""
    ok = status == "verified"
    color = "#1F7A4D" if ok else "#C43B2A"
    left, right = "code_agent", f"{status} · {detail}" if detail else status
    lw, rw = 8 + len(left) * 7, 10 + len(right) * 7
    left_e, right_e = escape(left), escape(right)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{lw + rw}" height="20" role="img" aria-label="{left_e}: {right_e}">
<title>{left_e}: {right_e}</title>
<rect width="{lw}" height="20" fill="#10241C"/>
<rect x="{lw}" width="{rw}" height="20" fill="{color}"/>
<g fill="#fff" font-family="JetBrains Mono,ui-monospace,monospace" font-size="11">
<text x="6" y="14" fill="#FF5A1F">{left_e}</text>
<text x="{lw + 6}" y="14">{right_e}</text>
</g>
</svg>"""
