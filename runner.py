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
    base_url = env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = env("OLLAMA_MODEL", "qwen3:8b")
    api_key = env("OLLAMA_API_KEY", "ollama")  # placeholder to satisfy OpenAI-compatible signature
    # ChatOpenAI in browser-use can target any OpenAI-compatible endpoint with base_url
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key, timeout=120)

def make_o3_llm() -> ChatOpenAI:
    # Uses OpenAI API directly (model="o3"). If you prefer o3-mini for cost, set OPENAI_MODEL=o3-mini
    model = env("OPENAI_MODEL", "o3")
    return ChatOpenAI(model=model)  # expects OPENAI_API_KEY in env

# Minimal Gemini client (planner/critic fallback) via google-generativeai
try:
    import google.generativeai as genai
except Exception:
    genai = None

async def gemini_text(prompt: str) -> str:
    if genai is None:
        raise RuntimeError("google-generativeai not installed. pip install google-generativeai")
    api_key = env("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY to use Gemini fallback")
    genai.configure(api_key=api_key)
    model = env("GEMINI_MODEL", "gemini-2.5-flash")
    # keep it simple; you can enhance with tools/function-calling later
    resp = await asyncio.to_thread(lambda: genai.GenerativeModel(model).generate_content(prompt))
    return resp.text or ""

# --------- Planner & Critic (cloud) ---------
PLANNER_SYSTEM = (
    "You are a meticulous planner for a browser automation agent. "
    "Given a user GOAL, produce a numbered, concrete, end-to-end plan of browser steps, "
    "including search queries when needed, target pages, success criteria for each step, "
    "and any data to extract. Prefer small composable steps. Output JSON with fields: "
    "{'subtasks': [{'title': str, 'instructions': str, 'success': str}]}"
)

CRITIC_SYSTEM = (
    "You are a strict critic of browser runs. Given the last observation and the intended subtask, "
    "diagnose failures and suggest one revised approach. Be concise. Output plain text."
)

async def plan_with_o3_then_gemini(goal: str) -> List[dict]:
    """
    Try OpenAI o3 for planning; fallback to Gemini 2.5 Flash.
    """
    llm = make_o3_llm()
    try:
        res = await llm.ainvoke(
            [
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "user", "content": f"GOAL:\n{goal}\nReturn JSON only."},
            ]
        )
        text = res.content if hasattr(res, "content") else str(res)
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
                {"role": "system", "content": CRITIC_SYSTEM},
                {"role": "user", "content": f"SUBTASK:\n{subtask}\n\nOBSERVATION:\n{observation}"},
            ]
        )
        return res.content if hasattr(res, "content") else str(res)
    except Exception as e:
        log(f"[critic] o3 error -> fallback to Gemini: {e}")
        return await gemini_text(CRITIC_SYSTEM + f"\n\nSUBTASK:\n{subtask}\n\nOBSERVATION:\n{observation}")

# --------- Serper search tool ---------
def build_tools() -> Tools:
    tools = Tools()
    SERPER_KEY = env("SERPER_API_KEY")

    @tools.action(description="Google search via Serper.dev. Returns top results as compact JSON string.")
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
                          title: str, instructions: str, cfg: RunConfig) -> str:
    """
    Try locally first. If we fail/stall, escalate once to cloud (o3) for this subtask only, then de-escalate.
    """
    # We steer the local agent using extend_system_message to bias it toward the current subtask.
    extend_msg = (
        "You are executing a single subtask inside a larger plan.\n"
        f"SUBTASK TITLE: {title}\n\n"
        f"DO:\n{instructions}\n\n"
        "Use the 'web_search' tool for Google queries when helpful.\n"
        "Keep going until the 'success' condition is met, then stop."
    )

    async def _attempt(llm: ChatOpenAI, tag: str) -> str:
        agent = Agent(
            task=title,
            llm=llm,
            tools=tools,
            browser=browser,
            extend_system_message=extend_msg,
            max_failures=cfg.max_failures_per_subtask,
            step_timeout=cfg.step_timeout_sec,
            # Consider setting a tiny 'page_extraction_llm' as local_llm again (keeps cost minimal)
            page_extraction_llm=local_llm,
        )
        log(f"[{tag}] starting agent for subtask: {title}")
        result = await agent.run()
        return str(result)

    # 1) Local attempt
    try:
        return await _attempt(local_llm, "local")
    except Exception as e_local:
        log(f"[local fail] {e_local}")

    # 2) Escalate to o3 just for this subtask
    cloud_llm = make_o3_llm()
    try:
        out = await _attempt(cloud_llm, "cloud-o3")
        return out
    except Exception as e_cloud:
        log(f"[cloud fail] {e_cloud}")

    # 3) Last ditch: ask critic for advice, then try local again quickly
    critic_note = await critic_with_o3_then_gemini(str(e_cloud), title)
    log("[critic advice]", critic_note)
    try:
        return await _attempt(local_llm, "local-after-critic")
    except Exception as e_final:
        raise RuntimeError(f"Subtask '{title}' failed after escalations: {e_final}") from e_final

async def main(goal: str):
    load_dotenv()
    tools = build_tools()
    browser = make_browser()
    local_llm = make_local_llm()
    cfg = RunConfig()

    # 1) Plan with o3 (fallback Gemini)
    subtasks = await plan_with_o3_then_gemini(goal)
    if not subtasks:
        raise RuntimeError("Planner returned no subtasks")

    # 2) Execute sequentially with local grinder, escalate per-subtask on failure
    for i, st in enumerate(subtasks, 1):
        title = st.get("title", f"Subtask {i}")
        instructions = st.get("instructions") or st.get("plan") or ""
        success_crit = st.get("success", "Complete the action as described.")
        log(f"=== [{i}/{len(subtasks)}] {title} ===")
        log("success when:", success_crit)
        result = await run_one_subtask(local_llm, browser, tools, title, instructions, cfg)
        log(f"[done] {title}\n{result}\n")

    log("✅ All subtasks complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runner.py \"<GOAL>\"", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))