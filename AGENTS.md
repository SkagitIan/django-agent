## AGENTS

These instructions apply to all autonomous or semi-autonomous scripts, tasks, or LLM-driven agents in this repository.

### Core Principles

1. **Reproducibility over autonomy** – every action must be traceable, reversible, and logged.
2. **Human in the loop** – no write, delete, or deploy operation runs without explicit confirmation from an authorized account.
3. **Fail closed** – if an environment variable, API key, or required dependency is missing, the agent exits gracefully.

---

### Development Guidelines

* Add or update **tests** for all new logic or API integrations.
* Keep commits focused; use descriptive, imperative messages.
* Follow **PEP 8**, include docstrings and type hints.
* Prefer `rg` for code searches.
* Small pull requests, clear change summaries, and evidence of testing.

---

### Secret Management

```python
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables safely
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
if not STRIPE_API_KEY:
    raise EnvironmentError("STRIPE_API_KEY not found. Check your .env file.")
```

**Rules**

* Never hard-code secrets or tokens.
* `.env` must never be committed.
* Agents must **read only**; they cannot write `.env` or export secrets dynamically.
* All secrets should be scoped per environment (`dev`, `staging`, `prod`) via OS vars.


### Agent Design Style 

* Keep them **functional**, not over-abstracted.
* Avoid “smart” error handling; fail loudly.
* Use plain classes or scripts — no heavy orchestration frameworks.
* Build modular pipelines: `ingest → enrich → output`, each callable in isolation.
* Each agent should have a **README** describing purpose, scope, and example runs.

