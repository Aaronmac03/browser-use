import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

from browser_use import Agent, Browser, ChatOpenAI, Tools
from browser_use.llm.messages import SystemMessage, UserMessage

# --------- Utilities ---------
def env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key, default)
    return os.path.expanduser(v) if isinstance(v, str) else v

def log(*args):
    print("[runner]", *args, flush=True)

# Chrome profile copy helper (helps avoid Chrome v136 default-profile CDP block)
def ensure_profile_copy_if_requested() -> tuple[str, str]:
    """
    If COPY_PROFILE_ONCE=1, copy CHROME_USER_DATA_DIR/<CHROME_PROFILE_DIRECTORY>
    into COPIED_USER_DATA_DIR/<CHROME_PROFILE_DIRECTORY>.
    Then return (user_data_dir_to_use, profile_dir_name)
    """
    src_user = env("CHROME_USER_DATA_DIR")
    prof = env("CHROME_PROFILE_DIRECTORY", "Default")
    dst_user = env("COPIED_USER_DATA_DIR", "./runtime/user_data")
    copy = os.getenv("COPY_PROFILE_ONCE", "0") == "1"

    if not src_user:
        raise RuntimeError("CHROME_USER_DATA_DIR not set")

    if copy:
        src_profile_path = Path(src_user).expanduser() / prof
        dst_user_path = Path(dst_user).expanduser()
        dst_profile_path = dst_user_path / prof
        dst_user_path.mkdir(parents=True, exist_ok=True)

        if dst_profile_path.exists():
            log(f"Profile copy exists: {dst_profile_path} (skipping copy)")
        else:
            log(f"Copying Chrome profile '{prof}' from {src_profile_path} -> {dst_profile_path}")
            # Copy but ignore heavy caches for speed/space
            def _ignore(dir, names):
                blacklist = {"Cache", "Code Cache", "Service Worker", "Default/Network", "Crashpad", "GrShaderCache"}
                return [n for n in names if n in blacklist]
            shutil.copytree(src_profile_path, dst_profile_path, ignore=_ignore)
            log("Copy complete.")
        return str(dst_user_path), prof
    else:
        # Use the system dir directly (works best with Chromium / or Chrome non-default profiles)
        return env("CHROME_USER_DATA_DIR"), prof

# --------- LLM clients ---------
def make_local_llm() -> ChatOpenAI:
    """Optimized local LLM configuration based on Qwen2.5-7B testing"""
    base_url = env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = env("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_k_m")
    api_key = env("OLLAMA_API_KEY", "ollama")  # placeholder to satisfy OpenAI-compatible signature
    
    return ChatOpenAI(
        model=model, 
        base_url=base_url, 
        api_key=api_key, 
        timeout=90,  # Balanced timeout for thorough work
        temperature=0.1,  # Slight creativity while maintaining consistency
        max_completion_tokens=2048,  # Sufficient for complex responses
        frequency_penalty=0.2,  # Reduce repetitive actions
        top_p=0.95,  # Focus on high-probability tokens
    )

def make_o3_llm() -> ChatOpenAI:
    """Cloud LLM for planning and critical thinking - optimized for capability over cost"""
    model = env("OPENAI_MODEL", "o3")  # Full o3, not o3-mini, per goal.md priorities
    
    # Configure for planning/reasoning tasks
    return ChatOpenAI(
        model=model,
        reasoning_effort='medium',  # Balance between speed and thoroughness for planning
        temperature=0.2,  # Some creativity for planning but still focused
        timeout=120,  # Adequate time for reasoning
    )  # expects OPENAI_API_KEY in env

# Minimal Gemini client (planner/critic fallback) via google-generativeai
try:
    import google.generativeai as genai
except Exception:
    genai = None

async def gemini_text(prompt: str) -> str:
    if genai is None:
        raise RuntimeError("google-generativeai not installed. pip install google-generativeai")
    api_key = env("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY to use Gemini fallback")
    genai.configure(api_key=api_key)
    model = env("GEMINI_MODEL", "gemini-2.5-flash")
    # keep it simple; you can enhance with tools/function-calling later
    resp = await asyncio.to_thread(lambda: genai.GenerativeModel(model).generate_content(prompt))
    return resp.text or ""

# --------- Planner & Critic (cloud) ---------
PLANNER_SYSTEM = (
    "You are an expert planner for a browser automation agent using local LLM execution with cloud planning. "
    "The executor has access to a web_search tool (Serper API) and full browser automation capabilities.\n\n"
    
    "STRATEGIC GUIDANCE:\n"
    "- For information gathering: Consider if web_search API can provide sufficient data quickly\n"
    "- For interactive tasks: Plan direct browser navigation and interaction\n"
    "- For complex workflows: Break into 2-4 comprehensive subtasks (not micro-steps)\n"
    "- Each subtask should accomplish a meaningful milestone\n"
    "- The local LLM executor is capable - trust it to handle multi-step actions within a subtask\n\n"
    
    "SUBTASK QUALITY:\n"
    "- Title: Clear, descriptive action (e.g., 'Search and analyze San Francisco weather')\n"
    "- Instructions: Detailed steps including what tools to use when appropriate\n"
    "- Success: Specific, measurable outcome that validates completion\n\n"
    
    "Given the user GOAL, create an optimal plan that leverages both API tools and browser automation intelligently. "
    "Output JSON: {'subtasks': [{'title': str, 'instructions': str, 'success': str}]}"
)

CRITIC_SYSTEM = (
    "You are an expert critic analyzing browser automation failures. The executor uses Qwen2.5-7B locally.\n\n"
    
    "COMMON FAILURE PATTERNS:\n"
    "- Malformed JSON output or corrupted responses\n"
    "- Repetitive actions without progress\n" 
    "- Session focus loss or navigation issues\n"
    "- Timeout due to overly complex single-step actions\n"
    "- Incorrect element selection or interaction\n\n"
    
    "ANALYSIS APPROACH:\n"
    "1. Identify the root cause from the observation\n"
    "2. Suggest ONE specific, actionable fix\n"
    "3. Consider if a different tool approach would work better\n"
    "4. Keep advice concise but actionable\n\n"
    
    "Output plain text with your diagnosis and recommended fix."
)

async def plan_with_o3_then_gemini(goal: str) -> List[dict]:
    """
    Try OpenAI o3 for planning; fallback to Gemini 2.5 Flash.
    """
    llm = make_o3_llm()
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(content=PLANNER_SYSTEM),
                UserMessage(content=f"GOAL:\n{goal}\nReturn JSON only."),
            ]
        )
        text = res.completion
        # Find JSON in the output
        jstart = text.find("{")
        jend = text.rfind("}")
        data = json.loads(text[jstart : jend + 1])
        return data.get("subtasks", [])
    except Exception as e:
        log(f"[planner] o3 error -> fallback to Gemini: {e}")
        out = await gemini_text(
            PLANNER_SYSTEM + "\n\nGOAL:\n" + goal + "\nReturn JSON only."
        )
        jstart = out.find("{")
        jend = out.rfind("}")
        data = json.loads(out[jstart : jend + 1])
        return data.get("subtasks", [])

async def critic_with_o3_then_gemini(observation: str, subtask: str) -> str:
    llm = make_o3_llm()
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(content=CRITIC_SYSTEM),
                UserMessage(content=f"SUBTASK:\n{subtask}\n\nOBSERVATION:\n{observation}"),
            ]
        )
        return res.completion
    except Exception as e:
        log(f"[critic] o3 error -> fallback to Gemini: {e}")
        return await gemini_text(CRITIC_SYSTEM + f"\n\nSUBTASK:\n{subtask}\n\nOBSERVATION:\n{observation}")

# --------- Serper search tool ---------
def build_tools() -> Tools:
    tools = Tools()
    SERPER_KEY = env("SERPER_API_KEY")

    @tools.action(description="Google search via Serper API - fast information gathering. Use for research, current data, facts. Returns structured JSON with results. Prefer this over browser search for pure information tasks.")
    def web_search(query: str, num_results: int = 6) -> str:
        if not SERPER_KEY:
            return json.dumps({"error": "SERPER_API_KEY not set"})
        try:
            payload = {"q": query, "num": max(1, min(int(num_results), 10))}
            headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
            r = httpx.post("https://google.serper.dev/search", headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            # Compact to essentials for the LLM
            def pick(it):
                return {k: it.get(k) for k in ("title", "link", "snippet")}
            results = [pick(x) for x in (data.get("organic", []) or [])]
            return json.dumps({"query": query, "results": results[:payload["num"]]})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return tools

# --------- Browser factory ---------
def make_browser() -> Browser:
    exe = env("CHROME_EXECUTABLE", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    user_dir, prof = ensure_profile_copy_if_requested()
    # We avoid allowed_domains entirely (per your request).
    # Notes:
    # - If Chrome refuses to start with your system profile (Chrome >=136), set COPY_PROFILE_ONCE=1.
    # - If you keep hitting CDP issues, install Chromium and point CHROME_EXECUTABLE to it.
    return Browser(
        executable_path=exe,
        user_data_dir=user_dir,
        profile_directory=prof,
        headless=False,
        devtools=False,
        # You can pass additional flags if needed:
        # args=["--disable-features=OptimizationGuideModelDownloading", "--disable-renderer-backgrounding"]
    )

# --------- Runner ---------
class RunConfig(BaseModel):
    max_failures_per_subtask: int = 2
    step_timeout_sec: int = 120

async def run_one_subtask(local_llm: ChatOpenAI, browser: Browser, tools: Tools,
                          title: str, instructions: str, cfg: RunConfig,
                          injected_state=None, progress_context: str = "") -> tuple[str, Any]:
    """
    Try locally first. If we fail/stall, escalate once to cloud (o3) for this subtask only, then de-escalate.
    """
    # Enhanced system message that leverages local LLM intelligence
    extend_msg = (
        "You are executing a single subtask inside a larger plan using optimized local LLM processing.\n\n"
        f"CURRENT SUBTASK: {title}\n\n"
        f"DETAILED INSTRUCTIONS:\n{instructions}\n\n"
        
        "EXECUTION STRATEGY:\n"
        "- You have web_search tool (Serper API) for quick information gathering\n"
        "- You have full browser automation capabilities for interactive tasks\n"
        "- Choose the most efficient approach - API for data, browser for interaction\n"
        "- Work methodically but efficiently toward the success criteria\n"
        "- Combine multiple related actions when logical\n"
        "- Only call 'done' when you have definitively achieved the success condition\n\n"
        
        "Stay focused on this specific subtask and complete it thoroughly before stopping."
    )

    async def _attempt(llm: ChatOpenAI, tag: str):
        # Optimize agent config based on model type
        is_local = "ollama" in llm.base_url if hasattr(llm, 'base_url') and llm.base_url else False
        
        agent = Agent(
            task=title,
            llm=llm,
            tools=tools,
            browser=browser,
            extend_system_message=(extend_msg + ("\n\nPRIOR PROGRESS:\n" + progress_context if progress_context else "")),
            max_failures=cfg.max_failures_per_subtask,
            step_timeout=cfg.step_timeout_sec,
            page_extraction_llm=local_llm,  # Always use local for cost efficiency
            # Optimal settings based on testing
            use_thinking=is_local,  # Enable reasoning for local model
            use_vision=False,  # Reduce processing load  
            max_actions_per_step=6 if is_local else 8,  # Balanced action grouping
            max_history_items=15 if is_local else 20,  # Appropriate context window
            flash_mode=False,  # Keep standard mode for reliability
            # Continuity settings
            injected_agent_state=injected_state,
            include_recent_events=True,
            directly_open_url=False,
        )
        log(f"[{tag}] starting agent for subtask: {title}")
        result = await agent.run()
        return agent, result

    async def _recover_session(reason: str) -> None:
        """Try to recover the browser session gracefully, then forcefully."""
        try:
            log(f"[recovery] Attempting graceful browser session recovery after: {reason}")
            await browser.stop()  # keep process if possible
            await browser.start()
            log("[recovery] Graceful recovery succeeded")
            return
        except Exception as e1:
            log(f"[recovery] Graceful recovery failed: {e1}. Trying hard reset...")
            try:
                await browser.kill()  # fully reset browser + event bus
                await browser.start()
                log("[recovery] Hard reset recovery succeeded")
            except Exception as e2:
                log(f"[recovery] Hard reset failed: {e2}")
                raise

    # 1) Local attempt
    try:
        agent, hist = await _attempt(local_llm, "local")
        return str(hist), getattr(agent, "state", None)
    except Exception as e_local:
        log(f"[local fail] {e_local}")
        # Try session recovery once, then retry local
        try:
            await _recover_session("local attempt failure")
            agent, hist = await _attempt(local_llm, "local-after-recover")
            return str(hist), getattr(agent, "state", None)
        except Exception as e_local_retried:
            log(f"[local retry fail] {e_local_retried}")

    # 2) Escalate to o3 just for this subtask
    cloud_llm = make_o3_llm()
    e_cloud = None
    try:
        agent, hist = await _attempt(cloud_llm, "cloud-o3")
        return str(hist), getattr(agent, "state", None)
    except Exception as exc:
        e_cloud = exc
        log(f"[cloud fail] {e_cloud}")
        # Try recovery then one more cloud attempt
        try:
            await _recover_session("cloud attempt failure")
            agent, hist = await _attempt(cloud_llm, "cloud-after-recover")
            return str(hist), getattr(agent, "state", None)
        except Exception as exc2:
            log(f"[cloud retry fail] {exc2}")

    # 3) Last ditch: ask critic for advice, then try local again quickly
    if e_cloud is not None:
        critic_note = await critic_with_o3_then_gemini(str(e_cloud), title)
        log("[critic advice]", critic_note)
    else:
        critic_note = "No cloud failure occurred"
        log("[critic advice]", critic_note)
    log("[critic advice]", critic_note)
    try:
        agent, hist = await _attempt(local_llm, "local-after-critic")
        return str(hist), getattr(agent, "state", None)
    except Exception as e_final:
        raise RuntimeError(f"Subtask '{title}' failed after escalations: {e_final}") from e_final

async def main(goal: str):
    load_dotenv()
    tools = build_tools()
    browser = make_browser()
    local_llm = make_local_llm()
    cfg = RunConfig()

    # Log configuration for transparency
    log(f"🎯 Goal: {goal}")
    log(f"🤖 Local model: {local_llm.model} (temp={local_llm.temperature}, timeout={local_llm.timeout}s)")
    log(f"☁️  Cloud model: {env('OPENAI_MODEL', 'o3')} for planning/critic")
    log(f"⚙️  Config: max_failures={cfg.max_failures_per_subtask}, step_timeout={cfg.step_timeout_sec}s")

    # 1) Plan with o3 (fallback Gemini)
    log("🧠 Planning with cloud LLM...")
    subtasks = await plan_with_o3_then_gemini(goal)
    if not subtasks:
        raise RuntimeError("Planner returned no subtasks")

    log(f"📋 Generated {len(subtasks)} subtasks")

    # 2) Execute sequentially with local grinder, escalate per-subtask on failure
    progress_notes: list[str] = []
    shared_state = None
    for i, st in enumerate(subtasks, 1):
        title = st.get("title", f"Subtask {i}")
        instructions = st.get("instructions") or st.get("plan") or ""
        success_crit = st.get("success", "Complete the action as described.")
        log(f"=== [{i}/{len(subtasks)}] {title} ===")
        log("success when:", success_crit)
        # Build continuity context from prior progress
        progress_context = "\n".join(progress_notes[-5:])  # keep last 5 notes
        result, shared_state = await run_one_subtask(
            local_llm, browser, tools, title, instructions, cfg,
            injected_state=shared_state, progress_context=progress_context,
        )
        # Record succinct note for next steps
        progress_note = f"[{i}] {title}: done"
        progress_notes.append(progress_note)
        log(f"[done] {title}\n{result}\n")

    log("✅ All subtasks complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runner.py \"<GOAL>\"", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
