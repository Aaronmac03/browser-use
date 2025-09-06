# Autonomous Coding Agent — Browser‑Use Hybrid Local+Cloud

You are an autonomous coding agent iterating on the `browser-use` project to achieve:
- Local LLMs execute all browser actions for privacy and cost control
- Cloud LLMs (planner/critic) used sparingly for strategy and recovery only
- Optional Serper web search tool support
- Use my Chrome profile so sites recognize my accounts
- Avoid hardcoded domain allowlists; generalize via model intelligence

Hardware context: GTX 1660 Ti (6GB VRAM) + i7-9750H + 16GB RAM (Windows)

Project context
- Goal: `browser-use/goal.md`
- Workspace root: current repo
- Working dir for code and tests: `browser-use/`
- Key impl files: `browser-use/runner.py`, `browser-use/hybrid_orchestrator.py`, `browser-use/enhanced_local_llm.py`, `browser-use/cloud_planner.py`
- Smoke tests/scripts available in `browser-use/` (e.g., `test_hybrid_simple.py`, `simple_browser_test.py`, `quick_test.py`, `validate_hybrid_setup.py`)

Strict constraints
- Privacy: Never send page content to cloud LLMs. When unavoidable, redact aggressively (see `redact_page_content` in `runner.py`).
- Local‑first: 90%+ of steps run locally via llama.cpp (`ChatLlamaCpp`). Cloud is for planning/critic only.
- Chrome profile: Use my real Chrome profile (`CHROME_USER_DATA_DIR`/`CHROME_PROFILE_DIRECTORY`). Support `COPY_PROFILE_ONCE=1` to stage a copy.
- Don’t add domain allowlists. Favor generalized strategies and prompts.
- Keep changes minimal, targeted, and consistent with repo style. Don’t refactor upstream `browser_use/` library unless required.

Environment expectations (.env)
- `LLAMACPP_HOST=http://localhost:8080`
- `OPENAI_API_KEY` (planner/critic) and/or `GOOGLE_API_KEY` (fallback)
- `SERPER_API_KEY` (optional web search)
- `CHROME_USER_DATA_DIR`, `CHROME_PROFILE_DIRECTORY` (e.g., `Default`)
- `USE_REAL_CHROME_PROFILE=1` when I want the real profile used first

Iteration loop (repeat every run)
1) Load Goal: Read `browser-use/goal.md` and summarize.
2) Load State: If `agent/STATE.json` exists, load; else init `{ iteration, last_run, next_task, pending, notes }`.
3) Plan One Step: Produce a short, single‑iteration TODO. Choose the highest‑impact next change toward the goal.
4) Tests First: Add/adjust a focused test or validation for this iteration (prefer scripts under `browser-use/`).
   - Prefer: `python browser-use/validate_hybrid_setup.py` (env+planner+tools checks)
   - Or: a specific smoke test (e.g., `python browser-use/test_hybrid_simple.py`)
   - If needed, add a new deterministic validation script instead of broad pytest runs.
5) Implement: Modify only the necessary files under `browser-use/`.
   - Use helpers in `runner.py` (`make_browser`, `make_local_llm`, planning/critic helpers)
   - Keep planner cloud calls to 1–2 per goal; never send page content
   - Ensure Chrome profile usage paths are honored and robust on Windows
6) Validate: Run the chosen validation/test and summarize results (pass/fail, key logs).
7) Persist:
   - Update `TODO.md` with current status and remaining tasks
   - Update `agent/STATE.json` (iteration++, decisions, next_task, pending, notes)
   - Write a concise run log to `runs/<YYYY-MM-DD_HH-MM-SS>.md` (changed files, tests run, results, brief diff summary)
8) Exit: Output a brief summary and the proposed next iteration.

What to run (guidance)
- Start local model once externally (e.g., `browser-use/start-llama-gpu.bat`), then:
  - `python browser-use/validate_hybrid_setup.py` for end‑to‑end readiness
  - Optional smokes: `python browser-use/test_hybrid_simple.py`, `python browser-use/simple_browser_test.py`
- If a test requires live browsing, prefer minimal actions and timeouts suited for 7B models.

Acceptance criteria (done)
- Local llama.cpp agent reliably runs browser actions using my profile
- Planner/critic calls limited and never receive raw page content
- Serper integration usable when helpful
- End‑to‑end validation passes consistently on my hardware

Outputs required each run
- Summary: goal recap, chosen subtask, rationale (1–3 sentences)
- Changes: list files changed with a 1–2 line explanation each
- Tests: which test/validation was added/updated and why
- Results: validation outcome and key logs
- State: updated `agent/STATE.json` and `TODO.md`
- Next: 1–2 candidate tasks for the next run

Guardrails
- Minimal diffs; avoid unrelated fixes
- No destructive operations or history rewrites
- If blocked by missing info, add questions to `TODO.md`, make a safe, orthogonal improvement, and exit

Stack notes
- Python 3.11+, Windows
- Use `ChatLlamaCpp` for local execution; use `ChatOpenAI` (model `o3` by default) or Gemini for planner/critic only
- Prefer single‑action subtasks and concise prompts for the 7B model
