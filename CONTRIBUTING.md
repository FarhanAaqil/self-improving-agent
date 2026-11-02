# Contributing

Thanks for wanting to help. This project runs untrusted code, so a few rules matter more than usual.

## Getting set up

```bash
pip install -e ".[dev]"
cp .env.example .env              # APP_ENV=development, no key needed locally
docker pull python:3.11-slim
npm --prefix frontend ci
```

Run the app with `uvicorn app.main:app --reload` and `npm --prefix frontend run dev`. No Groq key? Set `FAKE_LLM=true` for the scripted offline model.

## Before you open a PR

```bash
ruff check .
pytest -m "not integration"       # needs Docker for the sandbox tests; coverage gate is 75%
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
cd e2e && npm ci && npx playwright test   # against a running app with FAKE_LLM=true
```

CI runs all of the above. A PR is ready when every check is green.

## Ground rules

- **Never weaken the sandbox** (`app/sandbox.py`) without a new adversarial script in `app/adversarial/` that proves the change is safe. Each attack must print `BLOCKED` when stopped and `VULNERABILITY` when it gets through.
- **Never run generated code outside `run_code`.** No `exec`, no host subprocess.
- **Recalled memory is data, not instructions.** Keep it out of system prompts and keep it fenced.
- **Numbers must be measured.** The UI, README and API never show a metric that wasn't computed from a real run, and skipped checks are "N/A", not perfect.
- **No secrets in logs, URLs or the database.** Bring-your-own keys stay in memory for one run.

## Commit messages

Write them like you'd explain the change to a teammate: what changed and why, in plain sentences. No `feat:`/`fix:` prefixes.
