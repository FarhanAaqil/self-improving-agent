from groq import Groq

from app.config import GROQ_API_KEY, MODEL

_default_client: Groq | None = None


def _get_client() -> Groq:
    global _default_client
    if _default_client is None:
        _default_client = Groq(api_key=GROQ_API_KEY)
    return _default_client


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
    client = client_override or _get_client()
    model = model_override or MODEL

    prompt = f"""Task:
{task}

Python Code to audit:
{code}

Provide your security audit."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SECURITY_AUDIT_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
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

