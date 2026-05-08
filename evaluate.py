# ── evaluate.py ────────────────────────────────────────────
# Week 5: HumanEval Evaluation Engine
# Runs agent vs baseline on all 20 problems and reports pass@1.

import json, os, sys
from datetime import datetime
from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox import run_code
from config import LOG_DIR, MAX_RETRIES, MODEL

AGENT_SYSTEM = """You are an expert Python programmer.
Complete the given Python function. Return ONLY the complete function — no markdown, no backticks, no explanations."""

BASELINE_SYSTEM = """You are a Python programmer.
Complete the given Python function. Return only the function — no markdown, no backticks."""

def _clean(code: str) -> str:
    if "```" in code:
        lines = code.splitlines()
        code = "\n".join(l for l in lines if not l.strip().startswith("```"))
    return code.strip()

def _test_script(code: str, test: str) -> str:
    return f"{code}\n\n{test}\nprint('PASS')"

def run_baseline(problem: dict, client: Groq, model: str) -> dict:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": BASELINE_SYSTEM},
                {"role": "user",   "content": f"Complete this function:\n\n{problem['prompt']}"},
            ],
            temperature=0.1, max_tokens=1024,
        )
        code   = _clean(resp.choices[0].message.content)
        result = run_code(_test_script(code, problem["test"]))
        passed = result["success"] and "PASS" in (result["output"] or "")
        return {"passed": passed, "code": code, "error": result.get("error"), "attempts": 1}
    except Exception as e:
        return {"passed": False, "code": "", "error": str(e), "attempts": 1}

def run_agent(problem: dict, client: Groq, model: str, max_retries: int = MAX_RETRIES) -> dict:
    error_feedback = None
    for attempt in range(1, max_retries + 1):
        try:
            content = (
                f"Complete this function:\n\n{problem['prompt']}\n\n"
                f"Attempt {attempt-1} failed:\n{error_feedback}\n\nFix it."
                if error_feedback else
                f"Complete this function:\n\n{problem['prompt']}"
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM},
                    {"role": "user",   "content": content},
                ],
                temperature=0.1, max_tokens=1024,
            )
            code   = _clean(resp.choices[0].message.content)
            result = run_code(_test_script(code, problem["test"]))
            if result["success"] and "PASS" in (result["output"] or ""):
                return {"passed": True, "code": code, "error": None, "attempts": attempt}
            error_feedback = result.get("error") or "Tests failed."
        except Exception as e:
            error_feedback = str(e)
    return {"passed": False, "code": "", "error": error_feedback, "attempts": max_retries}

def evaluate_all(problems, client, model, max_retries=MAX_RETRIES, progress_cb=None):
    agent_res, base_res = [], []
    for i, p in enumerate(problems):
        bl = run_baseline(p, client, model)
        bl.update({"problem_id": p["id"], "difficulty": p["difficulty"], "entry_point": p["entry_point"]})
        base_res.append(bl)

        ag = run_agent(p, client, model, max_retries)
        ag.update({"problem_id": p["id"], "difficulty": p["difficulty"], "entry_point": p["entry_point"]})
        agent_res.append(ag)

        if progress_cb:
            progress_cb(i + 1, len(problems), p["id"])

    total        = len(problems)
    agent_pass   = sum(1 for r in agent_res  if r["passed"])
    base_pass    = sum(1 for r in base_res   if r["passed"])

    def by_diff(results):
        d = {}
        for r in results:
            k = r["difficulty"]
            d.setdefault(k, {"pass": 0, "total": 0})
            d[k]["total"] += 1
            if r["passed"]: d[k]["pass"] += 1
        return {k: {**v, "pct": round(v["pass"]/v["total"]*100, 1)} for k,v in d.items()}

    summary = {
        "timestamp": datetime.now().isoformat(), "model": model,
        "total_problems": total,
        "agent":    {"pass": agent_pass,  "total": total, "pass_at_1": round(agent_pass/total*100,1),  "by_difficulty": by_diff(agent_res),  "avg_attempts": round(sum(r["attempts"] for r in agent_res)/total,2)},
        "baseline": {"pass": base_pass,   "total": total, "pass_at_1": round(base_pass/total*100,1),   "by_difficulty": by_diff(base_res)},
        "improvement_pct": round((agent_pass - base_pass)/total*100, 1),
        "agent_results": agent_res, "baseline_results": base_res,
    }
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, "humaneval_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    return summary
