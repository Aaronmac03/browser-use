# Local + Cloud Hybrid Setup (Mac M4 16GB)

This document summarizes what we changed, why we changed it, and how the pieces fit together to achieve a low‑cost, privacy‑preserving browser agent that uses local models as “grunt” executors and cloud models for planning/critique.

## Goals
- Privacy and cost: prefer local LLM execution for routine/browser actions.
- Capability: use stronger cloud models for planning and failure analysis.
- Use existing Chrome profile (no allowlist) for real sessions with saved logins.
- Keep subtasks small and verifiable; lean on model intelligence instead of site‑specific code.

## Key Changes

- Local model client: switched to native `ChatOllama` for better structured‑output reliability with Ollama.
  - File: `runner.py` (import `ChatOllama`, return it from `make_local_llm`).
  - Reason: Ollama’s native `format=` handling is more consistent than the OpenAI‑compatible shim for tool/JSON outputs.

- Local model defaults: `qwen2.5:14b-instruct-q2_k` (fits on 16GB; good tool use for a 14B quant).
  - Files: `.env`, `.env.example` (`OLLAMA_HOST`, `OLLAMA_MODEL`).
  - Reason: 14B quant is a practical upper bound on 16GB and outperforms 7B for tool use.

- Agent tuning for local execution:
  - `use_thinking=False` when local (reduce verbosity and off‑track reasoning for smaller models).
  - `max_actions_per_step=4` when local (keep subtasks atomic and reduce timeouts/loops).
  - `max_history_items=12` when local (stay within context budget).
  - File: `runner.py` inside `run_one_subtask(... _attempt ...)`.

- Planner prompt adjustments: encourage 2–4 action, single‑site subtasks with on‑page verifiable outcomes.
  - File: `runner.py` (`PLANNER_SYSTEM`).
  - Reason: Smaller, single‑site subtasks are more reliable for local models and reduce failure loops.

- Browser profile handling: copy system Chrome profile once to avoid Chrome v136 CDP blocks; no allowlist.
  - File: `runner.py` (`ensure_profile_copy_if_requested`, `make_browser`).
  - Env: `CHROME_EXECUTABLE`, `CHROME_USER_DATA_DIR`, `CHROME_PROFILE_DIRECTORY`, `COPY_PROFILE_ONCE`, `COPIED_USER_DATA_DIR`.

- Escalation path retained: try local → recover → escalate this subtask to `o3` → recover → retry local with critic advice.
  - File: `runner.py` (`run_one_subtask` flow).
  - Reason: Keeps cost/privacy benefits while retaining a path to capability for hard steps.

## Rationale

- Local 7B–14B models struggle with long‑horizon multi‑site tasks and strict tool/JSON formatting. The hybrid design keeps cost and privacy while leveraging cloud for planning and failure recovery.
- Using `ChatOllama` reduces JSON/structured output flakiness vs. OpenAI‑compatible proxies.
- Tighter local agent settings (no thinking, smaller steps) reduce stalls/timeouts and improve completion rates.
- Planner constraints produce smaller, verifiable subtasks that local models can reliably execute.

## How to Use

1) Ensure Ollama is running and the model is pulled:
   - `OLLAMA_HOST=http://localhost:11434`
   - `OLLAMA_MODEL=qwen2.5:14b-instruct-q2_k`

2) Populate `.env` with cloud planner/critic keys (e.g., `OPENAI_API_KEY`) and optional `SERPER_API_KEY`.

3) Run:
   - `python runner.py "<YOUR GOAL>"`
   - The runner will plan in cloud, then execute each subtask locally, escalating only when needed.

## Notes

- If Chrome default profile fails to connect (v136+), set `COPY_PROFILE_ONCE=1` and re‑run once to create a local copy under `./runtime/user_data/<Profile>`.
- For heavier tasks, consider `qwen2.5:32b-instruct-q4_k_m` on larger memory machines; on 16GB, 14B is the practical ceiling.
- Groq Llama 4 is a cost‑effective cloud escalation alternative if it fits your privacy constraints.
