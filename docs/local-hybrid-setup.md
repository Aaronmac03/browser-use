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

- Local model defaults: **Updated to `qwen2.5:7b-instruct-q4_k_m`** (better performance than 14B Q2_K).
  - Files: `.env`, `.env.example` (`OLLAMA_HOST`, `OLLAMA_MODEL`).
  - Reason: **Q4_K_M quantization provides significantly better reasoning quality than Q2_K, even with smaller parameter count. 7B Q4_K_M outperforms 14B Q2_K for browser automation tasks.**

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

## Critical Bug Fixes (January 2025)

- **Fixed `scroll_to_text` UnboundLocalError**: Browser-use 0.7.1 had a critical bug where `js_result` variable was accessed outside its scope.
  - File: `browser_use/browser/watchdogs/default_action_watchdog.py` (lines 1590-1595).
  - Fix: Moved `js_result` access inside the `if not found:` block where it's defined.
  - Impact: Eliminated crashes during text scrolling operations.

- **Enhanced CDP session error handling**: Added graceful handling for "Session with given id not found" errors.
  - File: `browser_use/browser/watchdogs/default_action_watchdog.py` (lines 1519-1528).
  - Fix: Wrapped DOM.enable() in try-catch with specific session disconnection handling.
  - Impact: Better recovery from browser navigation-induced session losses.

## Performance Learnings (January 2025)

### Model Quantization Impact
- **Q2_K quantization is too aggressive** for browser automation tasks, even with larger models (14B).
- **Q4_K_M quantization provides dramatically better results** - 7B Q4_K_M outperforms 14B Q2_K.
- **Key metrics improved with Q4_K_M**:
  - Better tool selection and usage (especially web_search integration)
  - More coherent multi-step reasoning
  - Reduced repetitive/stuck behaviors
  - Successful task progression vs. getting stuck on first steps

### Web Search Integration Success
- **Serper API integration works excellently** with local models when properly quantized.
- Local models can effectively decide when to use web_search vs. browser navigation.
- Web search provides crucial information gathering that reduces browser navigation complexity.

### Browser Session Stability
- **Screenshot timeouts (8+ seconds)** remain a performance bottleneck.
- **CDP session disconnections** occur during navigation but are now handled gracefully.
- **Browser profile copying** (COPY_PROFILE_ONCE=1) is essential for Chrome v136+ compatibility.

## Rationale

- Local 7B–14B models struggle with long‑horizon multi‑site tasks and strict tool/JSON formatting. The hybrid design keeps cost and privacy while leveraging cloud for planning and failure recovery.
- **Quantization quality matters more than parameter count** for browser automation tasks.
- Using `ChatOllama` reduces JSON/structured output flakiness vs. OpenAI‑compatible proxies.
- Tighter local agent settings (no thinking, smaller steps) reduce stalls/timeouts and improve completion rates.
- Planner constraints produce smaller, verifiable subtasks that local models can reliably execute.

## How to Use

1) Ensure Ollama is running and the model is pulled:
   - `OLLAMA_HOST=http://localhost:11434`
   - `OLLAMA_MODEL=qwen2.5:7b-instruct-q4_k_m` (recommended for best performance)
   - Alternative: `qwen2.5:14b-instruct-q4_k_m` (if you have more RAM and want slightly better capability)

2) Populate `.env` with cloud planner/critic keys (e.g., `OPENAI_API_KEY`) and optional `SERPER_API_KEY`.

3) Run:
   - `python runner.py "<YOUR GOAL>"`
   - The runner will plan in cloud, then execute each subtask locally, escalating only when needed.

## Notes

- If Chrome default profile fails to connect (v136+), set `COPY_PROFILE_ONCE=1` and re‑run once to create a local copy under `./runtime/user_data/<Profile>`.
- **Model recommendations for 16GB RAM**:
  - **Best**: `qwen2.5:7b-instruct-q4_k_m` (optimal performance/memory balance)
  - **Alternative**: `qwen2.5:14b-instruct-q4_k_m` (higher capability, more memory usage)
  - **Avoid**: Any Q2_K quantizations (too aggressive, poor reasoning quality)
- Groq Llama 4 is a cost‑effective cloud escalation alternative if it fits your privacy constraints.
- **Browser-use 0.7.1 requires the bug fixes** documented above for reliable operation.


Key Insights for Complex Multi-Step Tasks
7B model is optimal for web navigation (speed vs capability balance)
Simple, focused steps work better than complex multi-action sequences
Clear completion criteria are essential for local LLMs
Element interaction reliability improved with text-based fallbacks
Task-specific prompting significantly improves success rates