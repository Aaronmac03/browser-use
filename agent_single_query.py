"""
Single-query version of the browser-use agent for testing
Usage: python agent_single_query.py "your query here"
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import json

from dotenv import load_dotenv

# Freshly load env (useful when switching providers)
for k in ("OPENAI_API_KEY", "GOOGLE_API_KEY"):
    if k in os.environ:
        del os.environ[k]
load_dotenv(override=True)

from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.agent.views import AgentHistoryList
from browser_use.llm import ChatOpenAI, ChatGoogle, SystemMessage, UserMessage

# ----------------------------
# Configuration
# ----------------------------
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('browser_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Force specific models (ignore env vars to avoid invalid model issues)
PLANNER_MODEL  = "gpt-4o-mini"      # OpenAI - forced default
EXECUTOR_MODEL = "gemini-2.0-flash"  # Google - forced default

# ----------------------------
# Terminal colors
# ----------------------------
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}🤖 Browser-Use Query Tool (Single Query){Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_status(message, color=Colors.BLUE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {message}{Colors.END}")

# ----------------------------
# Planner / Critic prompts (GENERAL — not task-specific)
# ----------------------------
PLANNER_SYS = """You are a high-reliability web plan generator for a browser automation agent (Browser-Use v0.6+).

Output: a concise, numbered, end-to-end plan that a non-deterministic agent can follow.

General best practices:
- Prefer first-party, in-app viewers (e.g., Google Drive/Docs/Sheets/Calendar) over downloading files.
- Avoid third-party file converters unless explicitly requested.
- Keep actions inside the smallest number of trusted domains needed to finish the task.
- Bring the correct tab to the foreground before interacting; avoid acting on background tabs.
- Use clear recovery strategies for common failures (missing element, wrong page, 2FA, rate-limit).
- Never perform actions outside the user's stated intent. If a step is ambiguous, proceed with the safest common-sense assumption and continue.

Write steps only — no commentary. Tailor them to this user instruction:
\"\"\"{task}\"\"\""""

CRITIC_SYS = """You are a strict QA checker for web-automation plans and outcomes.
Return either:
- A bullet list of concrete risks + one-line corrections, or
- Exactly: OK

Focus on: unnecessary downloads, third-party converters, wrong tab focus, domain drift, wrong formats, ambiguous steps, and missing completion criteria."""

# ----------------------------
# Small helper for LLM calls
# ----------------------------
async def chat_once(llm, user_prompt: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(UserMessage(content=user_prompt))
    resp = await llm.ainvoke(messages)
    return resp.completion

# ----------------------------
# Core runner
# ----------------------------
async def run_query(query: str, keep_browser_open: bool = False) -> bool:
    print_status("Initializing planner/critic system...", Colors.YELLOW)

    # Browser session
    browser_profile = BrowserProfile(
        user_data_dir=CHROME_PROFILE_DIR,
        keep_alive=keep_browser_open,
        headless=False
    )
    browser_session = BrowserSession(browser_profile=browser_profile)

    # LLMs
    planner_llm = ChatOpenAI(model=PLANNER_MODEL, api_key=os.getenv('OPENAI_API_KEY'))
    executor_llm = ChatGoogle(model=EXECUTOR_MODEL, api_key=os.getenv('GOOGLE_API_KEY'))

    print_status(f"Planner/Critic: {PLANNER_MODEL}", Colors.BLUE)
    print_status(f"Executor: {EXECUTOR_MODEL}", Colors.BLUE)

    try:
        # ---- Plan
        print_status("Generating plan...", Colors.YELLOW)
        plan = await chat_once(planner_llm, user_prompt=query, system_prompt=PLANNER_SYS)

        # ---- Critique plan
        print_status("Critiquing plan...", Colors.YELLOW)
        critique = await chat_once(planner_llm, user_prompt=f"Plan:\n{plan}", system_prompt=CRITIC_SYS)
        if "OK" not in critique.strip().upper():
            plan = plan + "\n\n# Critic adjustments\n" + critique

        # ---- Execute with the executor model (the one that actually drives the browser)
        print_status("Executing plan with browser agent...", Colors.YELLOW)
        print()
        agent = Agent(
            task=plan,
            llm=executor_llm,
            browser_session=browser_session,
            max_steps=25,
        )

        history: AgentHistoryList = await agent.run()

        # Pull result
        raw_result = history.final_result()
        if not raw_result:
            # Fallback: try to grab any extracted content
            for item in reversed(history.history):
                if getattr(item, 'result', None):
                    for action in item.result:
                        if getattr(action, 'extracted_content', None):
                            raw_result = action.extracted_content
                            break
                if raw_result:
                    break

        # ---- Final critic pass on the outcome
        print_status("Running critic validation...", Colors.YELLOW)
        critic_eval = await chat_once(
            planner_llm,
            user_prompt=f"Plan:\n{plan}\n\nOutcome:\n{raw_result or 'No specific result'}",
            system_prompt=CRITIC_SYS
        )

        final_result = raw_result or "No specific result extracted"

        print_status("✅ Query completed!", Colors.GREEN)

        # Console display
        print(f"\n{Colors.BOLD}Execution Result:{Colors.END}")
        print("-" * 40)
        print(final_result or "No specific result extracted.")
        print("-" * 40)

        print(f"\n{Colors.BOLD}Critic Assessment:{Colors.END}")
        print("-" * 40)
        print(critic_eval)
        print("-" * 40)

        await browser_session.kill()
        return True

    except Exception as e:
        print_status(f"❌ Error: {str(e)}", Colors.RED)
        await browser_session.kill()
        return False

# ----------------------------
# CLI
# ----------------------------
async def main():
    print_header()

    if len(sys.argv) < 2:
        print(f"{Colors.RED}Usage: python agent_single_query.py \"your query here\"{Colors.END}")
        print(f"{Colors.YELLOW}Example: python agent_single_query.py \"search for python tutorials on YouTube\"{Colors.END}")
        return

    query = " ".join(sys.argv[1:])

    # Require keys
    missing = []
    if not os.getenv('OPENAI_API_KEY'):
        missing.append('OPENAI_API_KEY (planner/critic)')
    if not os.getenv('GOOGLE_API_KEY'):
        missing.append('GOOGLE_API_KEY (executor)')
    if missing:
        print_status("❌ Missing required API keys:", Colors.RED)
        for k in missing:
            print_status(f"  - {k}", Colors.YELLOW)
        print_status("Add them to your .env and rerun.", Colors.YELLOW)
        return

    print(f"📁 Logs will be saved to: {LOGS_DIR.absolute()}")
    print(f"🌐 Using Chrome profile: {CHROME_PROFILE_DIR}")
    print(f"🎯 Query: {query}\n")

    success = await run_query(query, keep_browser_open=False)
    
    if success:
        print_status("🎉 Task completed successfully!", Colors.GREEN)
    else:
        print_status("💥 Task failed!", Colors.RED)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(0)