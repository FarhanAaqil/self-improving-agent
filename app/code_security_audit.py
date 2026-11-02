from app import llm

SECURITY_AUDIT_PROMPT = """You are a senior application security auditor reviewing Python code.
Analyze the code for software security vulnerabilities such as:
- Arbitrary code execution (eval, exec, pickle, unsafe yaml)
- Path traversal and arbitrary file access
- Injection risks (command, SQL, regex ReDoS)
- Insecure temporary files or hardcoded credentials
- Denial of service or unbounded resource exhaustion

Output format:
If no security risks are found:
SECURE

If any vulnerabilities are found, report each issue on its own line prefixed by its severity:
[CRITICAL] Issue description and remediation
[HIGH] Issue description and remediation
[MEDIUM] Issue description and remediation
[LOW] Issue description and remediation

Do NOT include pleasantries, introductory prose, or markdown code blocks.
Return ONLY "SECURE" or the tagged issue list."""


def audit_code_security(
    task: str,
    code: str,
    client_override=None,
    model_override: str | None = None,
) -> str:
    """Perform an LLM code review security audit and return 'SECURE' or tagged issues."""
    prompt = f"""Task:
{task}

Python Code to audit:
{code}

Provide your security audit."""

    raw = llm.chat(
        [
            {"role": "system", "content": SECURITY_AUDIT_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=model_override,
        temperature=0.1,
        max_tokens=800,
        client=client_override,
    )
    return _clean_security_output(raw)


def _clean_security_output(raw: str) -> str:
    text = raw.strip()
    if text.startswith("`") and text.endswith("`"):
        text = text.strip("`").strip()
    if text.upper().startswith("SECURE"):
        return "SECURE"
    return text


class CodeSecurityAudit:
    """
    CodeSecurityAudit agent performs static LLM analysis of code safety.
    Note: This is distinct from sandbox isolation (Docker containers and seccomp).
    This agent checks for architectural and library vulnerabilities inside code.
    """

    @staticmethod
    def audit(task: str, code: str, client_override=None, model_override: str | None = None) -> str:
        return audit_code_security(task, code, client_override=client_override, model_override=model_override)

