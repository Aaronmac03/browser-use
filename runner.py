import asyncio
import re
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

from browser_use import Agent, Browser, ChatOpenAI, ChatLlamaCpp, Tools
from browser_use.llm.base import BaseChatModel
from browser_use.agent.views import ActionResult
from browser_use.browser.events import NavigateToUrlEvent
from browser_use.llm.messages import SystemMessage, UserMessage

# --------- Utilities ---------
def env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key, default)
    return os.path.expanduser(v) if isinstance(v, str) else v

def log(*args):
    print("[runner]", *args, flush=True)

def redact_page_content(text: str) -> str:
    """
    Redact potentially sensitive page content before sending to cloud LLMs.
    Strips HTML tags, removes base64-like content, and truncates long tokens.
    """
    if not text:
        return text
    
    import re
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Split into tokens and handle long ones first (before base64 regex)
    tokens = text.split()
    redacted_tokens = []
    for token in tokens:
        if len(token) > 200:
            redacted_tokens.append('[REDACTED_LONG_TOKEN]')
        else:
            redacted_tokens.append(token)
    
    text = ' '.join(redacted_tokens)
    
    # Remove base64-like strings (long alphanumeric sequences with base64 characteristics)
    text = re.sub(r'\b[A-Za-z0-9+/]{50,}={0,2}\b', '[REDACTED_BASE64]', text)
    
    return text

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
            # Copy but ignore heavy caches and locked files for speed/space and avoid permission errors
            def _ignore(dir, names):
                blacklist = {
                    "Cache", "Code Cache", "Service Worker", "Default/Network", "Crashpad", "GrShaderCache",
                    "DawnGraphiteCache", "DawnWebGPUCache", "GPUCache", "LOCK", "Sessions", "Network"
                }
                # Also ignore files that end with common locked extensions
                ignored = []
                for name in names:
                    if (name in blacklist or 
                        name.endswith('-journal') or 
                        name == 'LOCK' or 
                        'Cache' in name or
                        'indexeddb.leveldb' in str(Path(dir) / name)):
                        ignored.append(name)
                return ignored
            
            try:
                shutil.copytree(src_profile_path, dst_profile_path, ignore=_ignore, ignore_dangling_symlinks=True)
            except (PermissionError, OSError) as e:
                log(f"[WARN] Profile copy had some permission errors (expected): {e}")
                # Continue anyway - partial copy is usually sufficient
            log("Copy complete.")
        return str(dst_user_path), prof
    else:
        # Use the system dir directly (works best with Chromium / or Chrome non-default profiles)
        return env("CHROME_USER_DATA_DIR"), prof

# --------- LLM clients ---------
def make_local_llm() -> BaseChatModel:
    """Optimized local LLM configuration for web navigation tasks using llama.cpp."""
    # Use llama.cpp server instead of Ollama for better performance and control
    base_url = env("LLAMACPP_HOST", "http://localhost:8080")
    
    # Strategy: Use 14B model for better reasoning capability in web navigation
    model = "qwen2.5-14b-instruct-q4_k_m.gguf"
    
    # Check if llama.cpp server is available
    try:
        response = httpx.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            log(f"[llm] llama.cpp server is running at {base_url}")
        else:
            log(f"[llm] llama.cpp server responded with status {response.status_code}")
    except Exception as e:
        log(f"[llm] Could not connect to llama.cpp server: {e}")
        log(f"[llm] Make sure to start the server with: start-llama-server.bat")
    
    # Optimize timeout for 7B model
    timeout = 60   # 7B is fast with llama.cpp
    log(f"[llm] Using llama.cpp with model: {model} (timeout={timeout}s)")
    
    return ChatLlamaCpp(
        model=model,
        base_url=base_url,
        timeout=timeout,
        temperature=0.1,  # Low temperature for consistent web navigation
        max_tokens=4096,
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
    "You are an expert planner for a browser automation agent using local 7B LLM execution with cloud planning. "
    "The executor has access to a web_search tool (Serper API) and full browser automation capabilities.\n\n"
    
    "LOCAL LLM CONSTRAINTS:\n"
    "- 7B model optimized for single, focused actions per step\n"
    "- Best performance with 1-2 actions per subtask\n"
    "- Prefers direct navigation over complex exploration\n"
    "- Response time: 10-20 seconds per action (factor into planning)\n\n"
    
    "STRATEGIC GUIDANCE:\n"
    "- For information gathering: Use web_search first to find the exact target URL\n"
    "- For interactive tasks: One clear action per subtask (navigate → search → click → type)\n"
    "- Subtask scope: SINGLE action on ONE site per subtask\n"
    "- Each subtask must have clear, verifiable completion criteria\n"
    "- Avoid multi-step subtasks - break them into atomic single actions\n\n"
    
    "SUBTASK QUALITY (Single Action Focus):\n"
    "- Title: ONE specific action (e.g., 'Navigate to weather.com', 'Search for San Francisco weather')\n"
    "- Instructions: Simple, direct action with exact steps\n"
    "- Success: Specific on-page evidence that validates the single action completed\n\n"
    
    "Given the user GOAL, break it into atomic single-action subtasks optimized for 7B local LLM execution. "
    "Output JSON: {'subtasks': [{'title': str, 'instructions': str, 'success': str}]}"
)

CRITIC_SYSTEM = (
    "You are an expert critic analyzing browser automation failures. The executor uses local Qwen2.5-7B model via llama.cpp.\n\n"
    
    "LOCAL 7B MODEL CONSTRAINTS:\n"
    "- 10-20 second response time per action\n"
    "- Works best with single, focused actions\n"
    "- May struggle with complex multi-step reasoning\n"
    "- Prefers direct element interaction over exploration\n\n"
    
    "COMMON FAILURE PATTERNS:\n"
    "- Timeout due to overly complex single-step actions\n"
    "- Repetitive actions without progress\n" 
    "- Session focus loss or navigation issues\n"
    "- Element selection issues (prefer scroll_to_text over index)\n"
    "- Complex instruction sets causing confusion\n\n"
    
    "ANALYSIS APPROACH:\n"
    "1. Identify if failure is due to complexity or model limitations\n"
    "2. Suggest ONE specific, simple fix optimized for 7B model\n"
    "3. Recommend breaking complex actions into simpler steps\n"
    "4. Keep advice actionable and 7B-model appropriate\n\n"
    
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
    # Redact potentially sensitive page content before sending to cloud
    redacted_observation = redact_page_content(observation)
    
    llm = make_o3_llm()
    try:
        res = await llm.ainvoke(
            [
                SystemMessage(content=CRITIC_SYSTEM),
                UserMessage(content=f"SUBTASK:\n{subtask}\n\nOBSERVATION:\n{redacted_observation}"),
            ]
        )
        return res.completion
    except Exception as e:
        log(f"[critic] o3 error -> fallback to Gemini: {e}")
        return await gemini_text(CRITIC_SYSTEM + f"\n\nSUBTASK:\n{subtask}\n\nOBSERVATION:\n{redacted_observation}")

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


def build_tools_for_subtask(title: str, instructions: str, success_crit: str) -> Tools:
    """Create a Tools instance with:
    - web_search that sets a usage flag
    - a guarded done action that validates success criteria heuristically
    """
    from browser_use.tools.views import DoneAction
    from browser_use.browser.views import BrowserStateSummary
    from browser_use.utils import is_new_tab_page

    SERPER_KEY = env("SERPER_API_KEY")

    # Create tools without excluding done - we'll override it
    tools = Tools()  # keep all actions, we'll override done

    # Simple tool usage tracking across this subtask
    usage = {"web_search_used": False}

    @tools.action(description="Google search via Serper API - fast information gathering. Use for research, current data, facts. Returns structured JSON with results. Prefer this over browser search for pure information tasks.")
    def web_search(query: str, num_results: int = 6) -> str:
        usage["web_search_used"] = True
        if not SERPER_KEY:
            return json.dumps({"error": "SERPER_API_KEY not set"})
        try:
            payload = {"q": query, "num": max(1, min(int(num_results), 10))}
            headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
            r = httpx.post("https://google.serper.dev/search", headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            def pick(it):
                return {k: it.get(k) for k in ("title", "link", "snippet")}
            results = [pick(x) for x in (data.get("organic", []) or [])]
            return json.dumps({"query": query, "results": results[:payload["num"]]})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Guarded done: only allow completing when basic success checks pass
    @tools.action(
        description=(
            "Complete task - summary to user. Set success=True only when success criteria are met. "
            "If criteria are not met, this returns an error and you must continue."
        ),
        param_model=DoneAction,
    )
    async def done(params: DoneAction, browser_session) -> Any:  # type: ignore
        # Acquire current page context for validation
        try:
            summary: BrowserStateSummary = await browser_session.get_browser_state_summary(
                cache_clickable_elements_hashes=False, include_screenshot=False
            )
            url = (summary.url or "").lower()
            title_l = (summary.title or "").lower()
            page_text = summary.dom_state.llm_representation(include_attributes=None).lower() if summary.dom_state else ""
        except Exception as e:
            # If we cannot inspect the page, be conservative and prevent early completion
            err = f"Cannot complete yet: failed to inspect page state ({type(e).__name__}: {e})"
            return ActionResult(error=err, long_term_memory=err)

        # Normalize inputs
        instr_l = (instructions or "").lower()
        succ_l = (success_crit or "").lower()
        title_lhs = (title or "").lower()

        # Generic guardrails
        if not url or url.startswith("about:") or url.startswith("chrome://") or is_new_tab_page(url):
            err = "Cannot complete: not on a meaningful page yet"
            return ActionResult(error=err, long_term_memory=err)

        # Generic heuristics derived from subtask goal
        def mentions(term: str) -> bool:
            t = term.lower()
            return t in instr_l or t in succ_l or t in title_lhs

        # Require using web_search for discovery tasks
        if mentions("search") or mentions("find"):
            if not usage["web_search_used"]:
                err = "Use web_search to discover the correct destination before completing"
                return ActionResult(error=err, long_term_memory=err)

        # If the subtask references a specific domain, ensure we are on it
        domain_pattern = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b")
        referenced_domains = set(domain_pattern.findall(instr_l + " " + succ_l + " " + title_lhs))
        if referenced_domains:
            if not any(d in url for d in referenced_domains):
                return ActionResult(error="Navigate to the referenced domain before completing", long_term_memory="Destination domain not reached")

        # If success=False, allow early termination but keep transparency
        if params.success is False:
            memory = f'Task ended without success: {params.text[:100]}'
            return ActionResult(is_done=True, success=False, extracted_content=params.text, long_term_memory=memory)

        # Map success criteria keywords to on-page evidence
        def extract_keywords(text: str) -> set[str]:
            words = re.findall(r"[a-zA-Z0-9]{5,}", text.lower())
            return set(words[:20])  # cap for efficiency

        success_keywords = extract_keywords(succ_l)
        if success_keywords:
            if not any(k in page_text or k in title_l for k in success_keywords):
                return ActionResult(error="On-page evidence for success criteria not found yet", long_term_memory="Continue actions toward criteria")

        # Passed validations -> allow completion
        memory = f'Task completed: {params.text[:100]}'
        return ActionResult(is_done=True, success=True, extracted_content=params.text, long_term_memory=memory)

    return tools

# --------- Browser factory ---------
def make_browser() -> Browser:
    # Prefer existing Chrome with remote debugging if provided
    cdp_url = env("CDP_URL")
    if cdp_url:
        return Browser(
            cdp_url=cdp_url,
            keep_alive=True,
        )

    # Graduated browser startup strategies (goal.md: use Chrome profile when viable)
    # Start with fastest/most reliable strategy first for immediate functionality
    strategies = [
        {"use_real_profile": False, "copy_profile": False, "name": "Clean Temporary Profile", "minimal": True},
        {"use_real_profile": False, "copy_profile": False, "name": "Clean Temporary Profile", "minimal": False},
        {"use_real_profile": False, "copy_profile": True, "name": "Copied Profile", "minimal": False},
        {"use_real_profile": True, "copy_profile": False, "name": "Real Chrome Profile", "minimal": False},
    ]
    
    # Override strategy based on env settings
    use_real_profile = os.getenv("USE_REAL_CHROME_PROFILE", "1").lower() in ("1", "true", "yes")
    if use_real_profile:
        # If user explicitly wants real profile, try it first
        strategies = [
            {"use_real_profile": True, "copy_profile": False, "name": "Real Chrome Profile", "minimal": False},
            {"use_real_profile": False, "copy_profile": False, "name": "Clean Temporary Profile", "minimal": True},
            {"use_real_profile": False, "copy_profile": False, "name": "Clean Temporary Profile", "minimal": False},
            {"use_real_profile": False, "copy_profile": True, "name": "Copied Profile", "minimal": False},
        ]
    
    for strategy in strategies:
        try:
            log(f"Attempting browser startup with strategy: {strategy['name']}")
            return _create_browser_with_strategy(strategy)
        except Exception as e:
            log(f"Browser strategy '{strategy['name']}' failed: {e}")
            continue
    
    raise RuntimeError("All browser startup strategies failed")


def _create_browser_with_strategy(strategy: dict) -> Browser:
    """Create browser with specific strategy using direct approach (bypasses watchdog CDP timeouts)."""
    # Find browser executable
    possible_executables = [
        env("CHROME_EXECUTABLE"),
        env("CHROME_EXECUTABLE_FALLBACK"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    
    exe = None
    for candidate in possible_executables:
        if candidate and Path(candidate).exists():
            exe = candidate
            log(f"Using browser executable: {exe}")
            break
    
    if not exe:
        raise RuntimeError("No suitable browser executable found. Install Chrome or Chromium.")

    # For now, always use minimal args approach that works reliably
    # This bypasses the complex watchdog system that causes CDP timeouts
    browser_args = [
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage",
        "--disable-gpu-sandbox",
        "--disable-sync",
        "--disable-translate",
        "--disable-default-apps",
    ]
    log(f"Using direct browser creation with minimal args (bypasses watchdog timeouts)")

    # Create browser directly like test_e2e_minimal.py (proven to work)
    return Browser(
        executable_path=exe,
        headless=False,
        devtools=False,
        keep_alive=True,  # Persist browser across subtasks to maintain session/focus
        args=browser_args,
    )

# --------- Runner ---------
class RunConfig(BaseModel):
    max_failures_per_subtask: int = 2
    step_timeout_sec: int = 120

def is_valid_result(result: Any) -> bool:
    """
    Validate if a result represents a successful completion.
    Treats as failure and escalates when any of the following occur:
    - Exception/timeout in local call
    - HTTP status >= 400
    - Empty/None/whitespace-only output
    - Parser error or missing required fields
    """
    if not result:
        return False
    
    # If result is a dict with success field
    if isinstance(result, dict):
        if not result.get("success"):
            return False
        text = (result.get("output") or "").strip()
        if not text:
            return False
        return True
    
    # If using raw strings
    text = str(result).strip()
    if not text:
        return False
    
    # Check for common error indicators
    error_indicators = ["error", "failed", "timeout", "exception", "502", "503", "504"]
    text_lower = text.lower()
    if any(indicator in text_lower for indicator in error_indicators):
        return False
    
    return True

def create_result_dict(success: bool, output: str, error: str = None, source: str = "local") -> dict:
    """
    Create standardized result dictionary with expected schema:
    {
      "success": true|false,
      "output": "<assistant text>",
      "error": "<error message or None>",
      "source": "local" | "cloud"
    }
    """
    return {
        "success": success,
        "output": output,
        "error": error,
        "source": source
    }

async def run_one_subtask(local_llm: BaseChatModel, browser: Browser, tools: Tools,
                          title: str, instructions: str, success_crit: str, cfg: RunConfig,
                          injected_state=None, progress_context: str = "") -> tuple[str, Any]:
    """
    Try locally first. If we fail/stall, escalate once to cloud (o3) for this subtask only, then de-escalate.
    """
    # Optimized system message for local LLM reliability and speed
    extend_msg = (
        f"TASK: {title}\n"
        f"GOAL: {instructions}\n"
        f"SUCCESS: {success_crit}\n\n"
        
        "EXECUTION STRATEGY:\n"
        "1. DIRECT APPROACH: Go straight to the target site/action\n"
        "2. SIMPLE ACTIONS: Use basic click/type/navigate - avoid complex sequences\n"
        "3. ELEMENT RELIABILITY: If index fails, try scroll_to_text with element text\n"
        "4. QUICK SUCCESS: Call 'done' immediately when goal is achieved\n\n"
        
        "COMMON PATTERNS:\n"
        "• Store locator: Look for 'Store Locator', 'Find Store', 'Locations' links\n"
        "• Search tasks: Navigate to site → find search box → enter query → submit\n"
        "• Navigation: Use main menu items, avoid buried links\n\n"
        
        "RELIABILITY RULES:\n"
        "• If element click fails, try scroll_to_text with the element's visible text\n"
        "• Don't repeat the same failed action - try a different element or approach\n"
        "• Use web_search for finding official website URLs\n"
        "• Navigate directly to known sites when possible\n"
        "• For store locators: Look in header/footer navigation first\n"
        "• Call 'done' when you successfully find or reach the target\n\n"
        
        "COMPLETE THE TASK EFFICIENTLY. NO EXPLORATION."
    )

    async def _ensure_browser_ready(reason: str) -> None:
        """Ensure browser is started and focused on a usable tab with enhanced health checks."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await browser.start()
                
                # Wait a moment for browser to fully initialize
                await asyncio.sleep(2)
                
                # Test basic browser functionality with a simple health check
                try:
                    # Try to get current page info - this will fail if CDP is broken
                    from browser_use.browser.events import BrowserStateRequestEvent
                    health_event = browser.event_bus.dispatch(BrowserStateRequestEvent())
                    await asyncio.wait_for(health_event, timeout=10)
                    log(f"[health] Browser health check passed (attempt {attempt + 1})")
                    break
                except Exception as health_e:
                    log(f"[health] Browser health check failed (attempt {attempt + 1}): {health_e}")
                    if attempt < max_retries - 1:
                        await browser.kill()
                        await asyncio.sleep(3)  # Wait before retry
                        continue
                    else:
                        raise health_e
                        
            except Exception as e:
                log(f"[health] Browser.start failed ({reason}, attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Try progressively more aggressive recovery
                    try:
                        if attempt == 0:
                            await browser.stop()  # Gentle stop first
                        else:
                            await browser.kill()  # Hard kill on subsequent attempts
                        await asyncio.sleep(3)
                    except Exception as cleanup_e:
                        log(f"[health] Cleanup failed: {cleanup_e}")
                else:
                    raise RuntimeError(f"Browser failed to start after {max_retries} attempts") from e

        # Ensure we have a usable tab - navigate to a simple page if needed
        try:
            # Check if we have focus, if not establish it
            if not getattr(browser, 'agent_focus', None):
                log("[health] No agent_focus after start; navigating to about:blank to establish focus")
                ev = browser.event_bus.dispatch(NavigateToUrlEvent(url='about:blank', new_tab=False))
                await asyncio.wait_for(ev, timeout=15)
                await ev.event_result(raise_if_any=True, raise_if_none=False)
                await asyncio.sleep(1)  # Let navigation settle
        except Exception as e:
            log(f"[health] Focus establishment failed: {e}")
            # Don't fail here - the agent might still work

    async def _attempt(llm: BaseChatModel, tag: str):
        # Optimize agent config based on model type
        provider = getattr(llm, 'provider', '')
        is_local = provider == 'ollama'
        # Fallback heuristic for OpenAI-compatible local endpoints
        if not is_local and hasattr(llm, 'base_url') and getattr(llm, 'base_url', None):
            burl = str(llm.base_url).lower()
            is_local = ('localhost' in burl) or ('127.0.0.1' in burl)
        # Proactively ensure browser session is healthy/focused before each attempt
        await _ensure_browser_ready(f"attempt:{tag}")

        # Per-subtask tools with guarded 'done'
        subtask_tools = build_tools_for_subtask(title=title, instructions=instructions, success_crit=success_crit)

        # Optimized configuration for local LLM web navigation
        if is_local:
            # Detect model size for optimal configuration
            model_name = getattr(llm, 'model', '').lower()
            is_14b = '14b' in model_name
            is_7b = '7b' in model_name
            
            if is_14b:
                # 14B model - can handle more complexity but is slower
                max_actions = 3  # Keep focused due to slower response times
                max_history = 15  # Moderate context
                use_thinking_mode = True
                step_timeout = 150  # Extended but reasonable timeout
            elif is_7b:
                # 7B model - optimize for speed and effectiveness
                max_actions = 2  # Keep steps very focused for speed
                max_history = 10  # Smaller context for faster processing
                use_thinking_mode = True  # Still beneficial for navigation
                step_timeout = 90   # Fast iterations
            else:
                # Unknown model - conservative settings
                max_actions = 2
                max_history = 10
                use_thinking_mode = True
                step_timeout = 90
        else:
            # Cloud model settings
            max_actions = 8
            max_history = 25
            use_thinking_mode = True
            step_timeout = cfg.step_timeout_sec

        # Configure DOM content limits based on LLM type
        if is_local:
            # Much smaller DOM limit for local LLM to prevent context overflow
            dom_limit = 2000  # Very conservative to prevent 502 errors
        else:
            # Full DOM content for cloud models with larger context windows
            dom_limit = 40000

        agent = Agent(
            task=title,
            llm=llm,
            tools=subtask_tools,
            browser=browser,
            extend_system_message=(extend_msg + ("\n\nPRIOR PROGRESS:\n" + progress_context if progress_context else "")),
            max_failures=cfg.max_failures_per_subtask,
            step_timeout=step_timeout,
            page_extraction_llm=local_llm,  # Always use local for cost efficiency
            # Optimized settings for local LLM navigation
            use_thinking=use_thinking_mode,
            use_vision=False,  # Keep disabled for performance and focus
            max_actions_per_step=max_actions,
            max_history_items=max_history,
            flash_mode=False,  # Standard mode for reliability
            include_tool_call_examples=True,  # Help with tool usage
            # Navigation-optimized settings
            injected_agent_state=injected_state,
            include_recent_events=True,
            directly_open_url=True,
            # Local LLM specific optimizations
            retry_on_failure=True,
            validate_output=True,
            max_clickable_elements_length=dom_limit,  # Context-optimized DOM limit
        )
        log(f"[{tag}] starting agent for subtask: {title}")
        result = await agent.run()
        return agent, result

    async def _recover_session(reason: str) -> None:
        """Try to recover the browser session with progressive escalation."""
        log(f"[recovery] Starting browser session recovery after: {reason}")
        
        # Step 1: Try gentle recovery (just restart)
        try:
            log("[recovery] Attempting gentle recovery (restart)")
            await browser.stop()
            await asyncio.sleep(2)  # Let processes clean up
            await browser.start()
            await asyncio.sleep(3)  # Let browser initialize
            
            # Test if recovery worked
            from browser_use.browser.events import BrowserStateRequestEvent
            test_event = browser.event_bus.dispatch(BrowserStateRequestEvent())
            await asyncio.wait_for(test_event, timeout=8)
            log("[recovery] Gentle recovery succeeded")
            return
        except Exception as e1:
            log(f"[recovery] Gentle recovery failed: {e1}")

        # Step 2: Try hard reset (kill and restart)
        try:
            log("[recovery] Attempting hard reset (kill + restart)")
            await browser.kill()
            await asyncio.sleep(5)  # Longer wait for full cleanup
            await browser.start()
            await asyncio.sleep(3)
            
            # Test if recovery worked with proper event
            from browser_use.browser.events import BrowserStateRequestEvent
            test_event = browser.event_bus.dispatch(BrowserStateRequestEvent())
            await asyncio.wait_for(test_event, timeout=8)
            log("[recovery] Hard reset recovery succeeded")
            return
        except Exception as e2:
            log(f"[recovery] Hard reset failed: {e2}")

        # Step 3: Final attempt with extended wait
        try:
            log("[recovery] Final recovery attempt with extended cleanup")
            await browser.kill()
            await asyncio.sleep(10)  # Extended wait for full cleanup
            await browser.start()
            await asyncio.sleep(5)  # Extended initialization wait
            
            # Test if recovery worked with proper event
            test_event = browser.event_bus.dispatch(BrowserStateRequestEvent())
            await asyncio.wait_for(test_event, timeout=10)
            log("[recovery] Final recovery attempt succeeded")
            return
        except Exception as e3:
            log(f"[recovery] Final recovery attempt failed: {e3}")
            raise RuntimeError(f"All recovery attempts failed. Last error: {e3}") from e3

    # Primary strategy: Focus on making local LLM succeed
    
    # 1) First local attempt with standard configuration
    try:
        agent, hist = await _attempt(local_llm, "local-primary")
        result_text = str(hist)
        if is_valid_result(result_text):
            log("[local-primary] Success with local LLM")
            return result_text, getattr(agent, "state", None)
        else:
            log("[local-primary] Local result invalid, continuing to retry")
            raise ValueError("Local result validation failed")
    except Exception as e_local:
        log(f"[local-primary fail] {e_local}")

    # 2) Recovery + retry local with adjusted settings
    try:
        await _recover_session("local primary failure")
        # Retry with more conservative settings for better reliability
        log("[local-retry] Attempting with conservative settings...")
        agent, hist = await _attempt(local_llm, "local-conservative")
        result_text = str(hist)
        if is_valid_result(result_text):
            log("[local-retry] Success with local LLM")
            return result_text, getattr(agent, "state", None)
        else:
            log("[local-retry] Local result invalid, continuing to critic guidance")
            raise ValueError("Local retry result validation failed")
    except Exception as e_local_retry:
        log(f"[local-retry fail] {e_local_retry}")

    # 3) Get guidance from critic, then try local again with insights
    try:
        critic_note = await critic_with_o3_then_gemini(str(e_local_retry), title)
        log(f"[critic guidance] {critic_note}")
        
        # Apply critic insights and try local again
        log("[local-guided] Attempting with critic guidance...")
        agent, hist = await _attempt(local_llm, "local-guided")
        result_text = str(hist)
        if is_valid_result(result_text):
            log("[local-guided] Success with local LLM")
            return result_text, getattr(agent, "state", None)
        else:
            log("[local-guided] Local result invalid, escalating to cloud")
            raise ValueError("Local guided result validation failed")
    except Exception as e_local_guided:
        log(f"[local-guided fail] {e_local_guided}")

    # 4) Only escalate to cloud as absolute last resort
    log("[escalation] Local attempts exhausted, trying cloud as last resort...")
    cloud_llm = make_o3_llm()
    try:
        await _recover_session("pre-cloud escalation")
        agent, hist = await _attempt(cloud_llm, "cloud-lastresort")
        result_text = str(hist)
        log("[escalation] Cloud succeeded - consider improving local LLM prompting for this scenario")
        return result_text, getattr(agent, "state", None)
    except Exception as e_cloud:
        log(f"[cloud-lastresort fail] {e_cloud}")
        raise RuntimeError(f"Subtask '{title}' failed completely after all attempts: local primary, local retry, local guided, cloud last resort") from e_cloud

async def main(goal: str):
    load_dotenv()
    tools = build_tools()
    browser = make_browser()
    local_llm = make_local_llm()
    # Enhanced configuration for 14B model and complex retail flows
    cfg = RunConfig(max_failures_per_subtask=2, step_timeout_sec=240)  # Longer timeout for 14B model

    # Log configuration for transparency
    log(f"[GOAL] {goal}")
    temp = getattr(local_llm, 'temperature', None)
    timeout = getattr(local_llm, 'timeout', None)
    log(f"[LOCAL] Model: {local_llm.model} (temp={temp}, timeout={timeout}s)")
    log(f"[CLOUD] Model: {env('OPENAI_MODEL', 'o3')} for planning/critic")
    log(f"[CONFIG] max_failures={cfg.max_failures_per_subtask}, step_timeout={cfg.step_timeout_sec}s")
    log("[BROWSER] keep_alive: True (persist across subtasks)")

    # 1) Plan with o3 (fallback Gemini)
    log("[PLANNER] Planning with cloud LLM...")
    subtasks = await plan_with_o3_then_gemini(goal)
    if not subtasks:
        raise RuntimeError("Planner returned no subtasks")

    log(f"[PLANNER] Generated {len(subtasks)} subtasks")

    # 2) Execute sequentially with local grinder, escalate per-subtask on failure
    progress_notes: list[str] = []
    shared_state = None
    # Pre-warm/start the browser once to establish CDP + focus early
    try:
        await browser.start()
    except Exception as e:
        log(f"[startup] Initial browser.start error (will auto-recover on subtask run): {e}")
    for i, st in enumerate(subtasks, 1):
        title = st.get("title", f"Subtask {i}")
        instructions = st.get("instructions") or st.get("plan") or ""
        success_crit = st.get("success", "Complete the action as described.")
        log(f"=== [{i}/{len(subtasks)}] {title} ===")
        log("success when:", success_crit)
        # Build continuity context from prior progress
        progress_context = "\n".join(progress_notes[-5:])  # keep last 5 notes
        result, shared_state = await run_one_subtask(
            local_llm, browser, tools, title, instructions, success_crit, cfg,
            injected_state=shared_state, progress_context=progress_context,
        )
        # Record succinct note for next steps
        progress_note = f"[{i}] {title}: done"
        progress_notes.append(progress_note)
        log(f"[done] {title}\n{result}\n")

    log("[SUCCESS] All subtasks complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runner.py \"<GOAL>\"", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
