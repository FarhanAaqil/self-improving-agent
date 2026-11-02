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
