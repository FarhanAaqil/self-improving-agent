from app import llm

SPEC_TESTS_PROMPT = """You are a senior QA engineer writing a spec for code that does not exist yet.

Write plain Python test functions from the task description alone:
- Name each test `test_<behaviour>` and use bare `assert` statements with a short message.
- 4 to 8 focused tests: the main behaviour plus real edge cases the task implies.
- Use exactly the function/class names the task states. If the task names none, pick one
  clear, conventional name and use it consistently.
- No imports of pytest, no test runner, no `if __name__` block, no implementation.
  The solution will already be defined in the same module when the tests run.
- Only standard library imports, and only if needed.
Return ONLY the Python test code."""

TEST_AGENT_PROMPT = """You are a senior QA engineer and Python test specialist.
Your task is to write clean, complete unit tests using pytest for the given Python code.

Requirements:
- Define comprehensive test functions prefixed with `test_`
- Cover common happy paths and boundary edge cases (empty collections, zero, negative numbers, extreme inputs)
- Use standard `assert` statements
- Return ONLY runnable Python code. No markdown fences, no explanations, no backticks."""


def generate_spec_tests(
    task: str,
    client_override=None,
    model_override: str | None = None,
    feedback: str | None = None,
) -> str:
    """Write tests from the task statement before any code exists (test-first repair loop)."""
    user = f"Task:\n{task}"
    if feedback:
        user += f"\n\nA previous version of these tests was judged wrong:\n{feedback}\nWrite corrected tests."
    raw = llm.chat(
        [
            {"role": "system", "content": SPEC_TESTS_PROMPT},
            {"role": "user", "content": user},
        ],
        model=model_override,
        temperature=0.2,
        max_tokens=1200,
        client=client_override,
    )
    return llm.clean_code(raw)


STRENGTHEN_PROMPT = """You are a QA engineer hardening a test suite.
You get a task, the tests written for it, the solution under test, and a list of small code
changes ("mutants") that the current tests failed to notice.

Write ADDITIONAL test functions that would fail for those changes.
- Take every expected value from the TASK statement. Never trust the solution's current
  behaviour as the source of truth; if the solution is wrong, your test should expose it.
- If a listed change does not alter any behaviour the task defines, skip it.
- Name tests `test_<behaviour>`, use bare `assert` statements with a short message.
- Do not repeat existing tests. No imports of pytest, no runner, no implementation.
Return ONLY the new test functions as Python code, or the single word NONE if nothing
meaningful can be added."""


def strengthen_tests(
    task: str,
    code: str,
    tests: str,
    survivors: list[dict],
    client_override=None,
    model_override: str | None = None,
) -> str | None:
    """Ask for extra spec tests covering behaviour the current tests leave unpinned."""
    gaps = "\n".join(
        f"- line {s.get('line')} (`{s.get('source', '')}`): {s.get('change')}" for s in survivors[:8]
    )
    user = (
        f"Task:\n{task}\n\nCurrent tests:\n{tests}\n\nSolution under test:\n{code}\n\n"
        f"Changes the tests did not notice:\n{gaps}"
    )
    raw = llm.chat(
        [
            {"role": "system", "content": STRENGTHEN_PROMPT},
            {"role": "user", "content": user},
        ],
        model=model_override,
        temperature=0.2,
        max_tokens=1000,
        client=client_override,
    )
    extra = llm.clean_code(raw)
    return extra if "def test_" in extra else None


def usable_tests(tests: str | None) -> bool:
    """Parseable Python with at least one test function. Parsing never runs the code."""
    import ast

    if not tests or "def test_" not in tests:
        return False
    try:
        tree = ast.parse(tests)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in tree.body)


def drop_tests(tests: str, names: list[str]) -> str:
    """Remove the named top-level test functions and return the rest."""
    import ast

    tree = ast.parse(tests)
    tree.body = [
        node for node in tree.body
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names)
    ]
    return ast.unparse(tree) + "\n"


def merge_tests(tests: str, extra: str) -> str:
    """Append extra tests, renaming any whose name already exists so nothing is shadowed."""
    import re

    existing = set(re.findall(r"^def (test_\w+)\(", tests, re.M))

    def rename(match: re.Match) -> str:
        name = match.group(1)
        while name in existing:
            name += "_strict"
        existing.add(name)
        return f"def {name}("

    return tests.rstrip() + "\n\n\n" + re.sub(r"^def (test_\w+)\(", rename, extra.strip(), flags=re.M) + "\n"


def generate_unit_tests(
    task: str,
    code: str,
    client_override=None,
    model_override: str | None = None,
) -> str:
    """Take approved code and task, generate unit tests, and return them as a string."""
    prompt = f"""Task:
{task}

Approved Python Code:
{code}

Write standalone pytest unit tests testing this code."""

    raw = llm.chat(
        [
            {"role": "system", "content": TEST_AGENT_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=model_override,
        temperature=0.2,
        max_tokens=1500,
        client=client_override,
    )
    return llm.clean_code(raw)
