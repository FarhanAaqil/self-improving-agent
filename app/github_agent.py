"""GitHub Pull Request Automation Agent.

Given a run_id, commits the verified solution to a new branch and opens a Pull Request.
Fully no-op when GITHUB_TOKEN is not set, verified at import time.
"""

import base64
import logging
import re
from typing import Any

import httpx

from app.config import GITHUB_ALLOWED_REPOS, GITHUB_REPO, GITHUB_TOKEN
from app.db import get_run_with_attempts

logger = logging.getLogger("self_improving_agent.github")

# Checked at import time — if token is missing or placeholder, agent is completely inert
IS_GITHUB_CONFIGURED: bool = bool(
    GITHUB_TOKEN and GITHUB_TOKEN.strip() and GITHUB_TOKEN != "mock-token"
)

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "error": message, "pr_url": None}


def _fence(text: str) -> str:
    """Wrap text in a code fence longer than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def open_pull_request_for_run(
    run_id: str,
    repo: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Open a Pull Request containing the verified solution for run_id.

    Returns a status dict:
      - {"status": "skipped", "reason": "...", "pr_url": None} if GITHUB_TOKEN not configured
      - {"status": "success", "pr_url": "https://...", "pr_number": 42} on success
      - {"status": "error", "error": "...", "pr_url": None} on failure
    """
    if not IS_GITHUB_CONFIGURED:
        return {
            "status": "skipped",
            "reason": "GITHUB_TOKEN is not configured in environment.",
            "pr_url": None,
        }

    target_repo = (repo or GITHUB_REPO or "").strip()
    if not _REPO_PATTERN.match(target_repo):
        return _error(f"Invalid target repository format: '{target_repo}'. Expected 'owner/repo'.")
    if target_repo not in GITHUB_ALLOWED_REPOS:
        return _error(
            f"Repository '{target_repo}' is not in GITHUB_ALLOWED_REPOS; refusing to push there."
        )

    run_data = get_run_with_attempts(run_id)
    if not run_data:
        return _error(f"Run '{run_id}' not found in database.")

    passing_attempt = next((a for a in run_data.get("attempts", []) if a.get("success")), None)
    if run_data.get("final_status") != "success" or passing_attempt is None:
        return _error("Only runs that passed verification can be opened as a pull request.")
    solution_code = passing_attempt.get("generated_code", "")

    task_desc = run_data.get("task_description", "Unknown Task")
    safe_run_id = re.sub(r"[^a-zA-Z0-9_-]", "", run_id)
    if not safe_run_id:
        return _error(f"Invalid run_id: '{run_id}' contains no valid characters.")
    branch_name = f"agent/solution-{safe_run_id}"
    file_path = f"solutions/solution_{safe_run_id}.py"

    http_client = client or httpx.Client(timeout=15.0)
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_url = f"https://api.github.com/repos/{target_repo}"

    try:
        # 1. Determine base branch (check main, fallback to master)
        base_branch = "main"
        ref_resp = http_client.get(f"{base_url}/git/ref/heads/main", headers=headers)
        if ref_resp.status_code != 200:
            ref_resp = http_client.get(f"{base_url}/git/ref/heads/master", headers=headers)
            base_branch = "master"
            if ref_resp.status_code != 200:
                return _error(f"Could not retrieve base branch reference from {target_repo}.")

        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create agent solution branch (422 = it already exists, which is fine)
        create_branch_resp = http_client.post(
            f"{base_url}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if create_branch_resp.status_code not in (201, 422):
            logger.warning("Branch creation failed: %s", create_branch_resp.text)
            return _error(f"GitHub refused to create branch '{branch_name}'.")

        # 3. Create the solution file, or update it if a previous click already made it
        payload = {
            "message": f"Verified solution for {run_id}",
            "content": base64.b64encode(solution_code.encode("utf-8")).decode("utf-8"),
            "branch": branch_name,
        }
        file_url = f"{base_url}/contents/{file_path}"
        file_resp = http_client.put(file_url, headers=headers, json=payload)
        if file_resp.status_code == 422:
            existing = http_client.get(file_url, headers=headers, params={"ref": branch_name})
            if existing.status_code == 200:
                payload["sha"] = existing.json().get("sha")
                file_resp = http_client.put(file_url, headers=headers, json=payload)
        if file_resp.status_code not in (200, 201):
            logger.warning("File commit failed: %s", file_resp.text)
            return _error(f"GitHub refused to commit '{file_path}'.")

        # 4. Open Pull Request
        score = passing_attempt.get("quality_overall_score")
        pr_body = (
            f"## Verified solution for `{run_id}`\n\n"
            f"### Task\n"
            f"{_fence(task_desc)}\n\n"
            f"### Execution summary\n"
            f"- **Status:** `{run_data.get('final_status')}`\n"
            f"- **Attempts used:** {run_data.get('total_attempts')}\n"
            f"- **Passed on attempt:** {passing_attempt.get('attempt_number')}\n"
            f"- **Quality score:** {score if score is not None else 'N/A'}\n\n"
            f"---\n"
            f"*Opened by the Self-Improving Code Agent.*"
        )

        pr_resp = http_client.post(
            f"{base_url}/pulls",
            headers=headers,
            json={
                "title": f"Agent solution: {run_id} — {task_desc[:60]}",
                "head": branch_name,
                "base": base_branch,
                "body": pr_body,
            },
        )

        if pr_resp.status_code == 422:
            # A PR for this branch is already open; hand that one back instead of failing
            owner = target_repo.split("/")[0]
            open_prs = http_client.get(
                f"{base_url}/pulls",
                headers=headers,
                params={"head": f"{owner}:{branch_name}", "state": "open"},
            )
            if open_prs.status_code == 200 and open_prs.json():
                pr_data = open_prs.json()[0]
                return {
                    "status": "success",
                    "pr_url": pr_data.get("html_url"),
                    "pr_number": pr_data.get("number"),
                    "branch": branch_name,
                    "already_open": True,
                }
            return _error("GitHub rejected the pull request (422).")

        if pr_resp.status_code != 201:
            logger.warning("PR creation failed: %s", pr_resp.text)
            return _error(f"GitHub refused to open the pull request ({pr_resp.status_code}).")

        pr_data = pr_resp.json()
        return {
            "status": "success",
            "pr_url": pr_data.get("html_url"),
            "pr_number": pr_data.get("number"),
            "branch": branch_name,
        }

    except Exception as e:
        logger.error("Exception while creating PR for %s: %s", run_id, e, exc_info=True)
        return _error("Unexpected error while talking to GitHub. Check server logs.")
    finally:
        if client is None:
            http_client.close()
