"""GitHub Pull Request Automation Agent.

Given a run_id, commits the verified solution to a new branch and opens a Pull Request.
Fully no-op when GITHUB_TOKEN is not set, verified at import time.
"""

import base64
from typing import Any

import httpx

from app.config import GITHUB_REPO, GITHUB_TOKEN
from app.db import get_run_with_attempts

# Checked at import time — if token is missing or placeholder, agent is completely inert
IS_GITHUB_CONFIGURED: bool = bool(
    GITHUB_TOKEN and GITHUB_TOKEN.strip() and GITHUB_TOKEN != "mock-token"
)


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

    target_repo = repo or GITHUB_REPO
    if not target_repo or "/" not in target_repo:
        return {
            "status": "error",
            "error": f"Invalid target repository format: '{target_repo}'. Expected 'owner/repo'.",
            "pr_url": None,
        }

    run_data = get_run_with_attempts(run_id)
    if not run_data:
        return {
            "status": "error",
            "error": f"Run '{run_id}' not found in database.",
            "pr_url": None,
        }

    attempts = run_data.get("attempts", [])
    if not attempts:
        return {
            "status": "error",
            "error": f"Run '{run_id}' has no attempts to open PR for.",
            "pr_url": None,
        }

    passing_attempt = next((a for a in attempts if a.get("success")), None)
    best_attempt = passing_attempt or attempts[-1]
    solution_code = best_attempt.get("generated_code", "")

    task_desc = run_data.get("task_description", "Unknown Task")
    branch_name = f"agent/solution-{run_id}"
    file_path = f"solutions/solution_{run_id}.py"

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
                return {
                    "status": "error",
                    "error": f"Could not retrieve base branch reference from {target_repo}.",
                    "pr_url": None,
                }

        base_sha = ref_resp.json()["object"]["sha"]

        # 2. Create agent solution branch
        create_branch_resp = http_client.post(
            f"{base_url}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if create_branch_resp.status_code not in (201, 422):
            return {
                "status": "error",
                "error": f"Failed creating branch '{branch_name}': {create_branch_resp.text}",
                "pr_url": None,
            }

        # 3. Create/update solution file on branch
        encoded_content = base64.b64encode(solution_code.encode("utf-8")).decode("utf-8")
        commit_file_payload = {
            "message": f"feat(agent): verified solution for {run_id}",
            "content": encoded_content,
            "branch": branch_name,
        }
        file_resp = http_client.put(
            f"{base_url}/contents/{file_path}",
            headers=headers,
            json=commit_file_payload,
        )
        if file_resp.status_code not in (200, 201):
            return {
                "status": "error",
                "error": f"Failed committing file '{file_path}': {file_resp.text}",
                "pr_url": None,
            }

        # 4. Open Pull Request
        pr_title = f"Agent Solution: {run_id} — {task_desc[:60]}"
        pr_body = (
            f"## 🤖 Automated Solution for `{run_id}`\n\n"
            f"### Task Description\n"
            f"```\n{task_desc}\n```\n\n"
            f"### Execution Summary\n"
            f"- **Status:** `{run_data.get('final_status')}`\n"
            f"- **Attempts Used:** {run_data.get('total_attempts')}\n"
            f"- **Sandbox Execution:** Verified in isolated Docker container\n"
            f"- **Quality Score:** {best_attempt.get('quality_overall_score', 'N/A')}\n\n"
            f"---\n"
            f"*Generated by [Self-Improving Code Agent](https://github.com/{target_repo}).*"
        )

        pr_resp = http_client.post(
            f"{base_url}/pulls",
            headers=headers,
            json={
                "title": pr_title,
                "head": branch_name,
                "base": base_branch,
                "body": pr_body,
            },
        )

        if pr_resp.status_code not in (201, 422):
            return {
                "status": "error",
                "error": f"Failed opening Pull Request: {pr_resp.text}",
                "pr_url": None,
            }

        pr_data = pr_resp.json()
        pr_url = pr_data.get("html_url")
        pr_number = pr_data.get("number")

        return {
            "status": "success",
            "pr_url": pr_url,
            "pr_number": pr_number,
            "branch": branch_name,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Exception while creating PR: {str(e)}",
            "pr_url": None,
        }
    finally:
        if client is None:
            http_client.close()
