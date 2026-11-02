# Legacy results (not comparable)

These files came from the old evaluator, before the Phase 2 rewrite. They are kept for history only:

- The problem set was a simplified 50-problem paraphrase of HumanEval with 2–5 asserts per problem, not the official tests.
- On a retry the agent saw the failing assertion line, which leaked the hidden tests.
- The ~62 ms average latency shows they ran on the host, not in the Docker sandbox.

Current numbers come from `python -m eval.benchmark` (official HumanEval, sandboxed, no test leakage).
