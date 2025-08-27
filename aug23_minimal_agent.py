"""
Minimal Aug23 Playbook Implementation - Copy-pasteable config sketch

This is the minimal implementation from the aug23 playbook that you can slot into any project.
Includes the core optimization patterns without extensive scaffolding.
"""

import asyncio
from browser_use import Agent, Controller, BrowserSession, BrowserProfile
from browser_use.llm import ChatOpenAI, ChatAnthropic
from browser_use.agent.views import AgentHistoryList
from pathlib import Path

# --- Models (with auto-escalation strategy) ---
planner_llm = ChatOpenAI(model="gpt-4o-mini")  # Cheaper reasoning model
executor_llm = ChatOpenAI(model="o3")           # Default executor
strong_llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")  # Escalation model

# --- Controller with structured output (swap in a Pydantic model for extraction tasks) ---
controller = Controller(output_model=None)

# --- Browser profile/session (stability first) ---
profile = BrowserProfile(
    wait_for_network_idle_page_load_time=3.0,
    minimum_wait_page_load_time=0.5,
    maximum_wait_page_load_time=8.0,
    wait_between_actions=0.7,
    default_timeout=10_000,
    default_navigation_timeout=45_000,
    allowed_domains=['*'],
)
session = BrowserSession(browser_profile=profile)

# --- Global state tracking for hooks ---
consecutive_failures = 0
model_escalated = False

# --- Hooks implementation ---
async def on_step_start(agent, step_info=None):
    """Hook: Take screenshots and check domain drift."""
    # Take screenshot for visual verification
    try:
        timestamp = f"{Path.cwd().name}_{len(agent.history)}"
        screenshot_dir = Path("browser_queries/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        await agent.controller.page.screenshot(path=f"{screenshot_dir}/{timestamp}.png")
        print(f"📸 Screenshot: {timestamp}.png")
    except Exception as e:
        print(f"Screenshot failed: {e}")

async def on_step_end(agent, step_result=None):
    """Hook: Handle failures and model escalation."""
    global consecutive_failures, model_escalated
    
    # Check if step failed (simplified check)
    last_action_success = True
    if hasattr(agent, 'history') and agent.history:
        last_step = agent.history[-1] if agent.history else {}
        last_action_success = not hasattr(last_step, 'error') or last_step.error is None
    
    if last_action_success:
        consecutive_failures = 0
    else:
        consecutive_failures += 1
        print(f"❌ Step failed. Consecutive failures: {consecutive_failures}")
        
        # Auto-escalation: if ≥2 consecutive failures, swap to strong model
        if consecutive_failures >= 2 and not model_escalated:
            print(f"🔄 Escalating to strong model")
            agent.llm = strong_llm
            model_escalated = True

# --- Custom Actions (implement as needed) ---
async def safe_go_to(page, url):
    """Navigate → wait-for-idle → verify URL contains expected host."""
    await page.goto(url)
    await page.wait_for_load_state('networkidle', timeout=15000)
    # Add URL verification logic as needed
    return page.url

async def js_click(page, selector):
    """JavaScript click fallback when standard click fails."""
    return await page.evaluate(f"document.querySelector('{selector}')?.click()")

async def ask_human(question):
    """Breakpoint handoff for human input."""
    print(f"\n🤖 HUMAN INPUT NEEDED: {question}")
    return input("👤 Your response: ")

# --- Main execution function ---
async def run_optimized_task(task_description, use_human_gates=False, output_model=None):
    """Run a task with aug23 optimizations."""
    
    # Create agent with planner/executor strategy
    agent = Agent(
        task=task_description,
        llm=executor_llm,
        planner_llm=planner_llm,
        controller=Controller(output_model=output_model),
        use_vision=True,
        vision_detail_level="auto",  # Set "low" for simple UIs to cut cost
        save_conversation_path="browser_queries/conversations",
    )
    
    # Human-in-the-loop confirmation gate
    if use_human_gates:
        danger_keywords = ['buy', 'submit', 'send', 'transfer', 'delete', 'purchase']
        if any(keyword in task_description.lower() for keyword in danger_keywords):
            confirm = ask_human(f"About to: {task_description}. Continue?")
            if confirm.lower() not in ['yes', 'y']:
                return {"success": False, "error": "User cancelled"}
    
    try:
        # Execute with stability-first config
        history = await agent.run(
            max_steps=60,
            max_actions_per_step=2,
            max_failures=3,
            retry_delay=10,
        )
        
        # Process results using AgentHistoryList helpers
        history_list = AgentHistoryList(history)
        
        # Extract artifacts and save compact state memo
        result = {
            "success": history_list.is_complete(),
            "data": history_list.extract_data(),
            "final_url": agent.controller.page.url if agent.controller.page else None,
            "steps_taken": len(history),
        }
        
        # Save state memo for next run's message_context
        state_memo_file = Path("browser_queries/state_memos/latest.json")
        state_memo_file.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(state_memo_file, 'w') as f:
            json.dump({
                "last_url": result["final_url"],
                "last_success": task_description if result["success"] else None,
                "last_error": "Task failed" if not result["success"] else None,
            }, f, indent=2)
        
        return result
        
    except Exception as e:
        return {
            "success": False, 
            "error": str(e),
            "final_url": None,
            "steps_taken": 0
        }

# --- Example usage ---
async def main():
    """Example usage of the optimized agent."""
    
    # Example 1: Simple search with extraction
    print("🔄 Running search task...")
    result = await run_optimized_task(
        "Search for 'browser automation' and extract the first 3 results with titles and URLs"
    )
    print(f"✅ Search result: {result}")
    
    # Example 2: Task with human confirmation gates
    print("\n🔄 Running task with human gates...")
    result = await run_optimized_task(
        "Navigate to a contact form and submit test data",
        use_human_gates=True
    )
    print(f"✅ Form result: {result}")

# --- Cost-efficient alternative using Gemini Flash ---
async def run_cost_efficient_task(task_description):
    """Alternative with cost-efficient model for steady-state tasks."""
    from browser_use.llm import ChatGoogle
    
    cost_efficient_llm = ChatGoogle(model="gemini-2.5-flash")
    
    agent = Agent(
        task=task_description,
        llm=cost_efficient_llm,
        planner_llm=planner_llm,  # Still use good planner
        controller=Controller(),
        use_vision=True,
        vision_detail_level="low",  # Cut vision costs
        save_conversation_path="browser_queries/conversations",
    )
    
    history = await agent.run(max_steps=30, max_actions_per_step=2)
    return AgentHistoryList(history)

if __name__ == "__main__":
    # Quick test
    asyncio.run(main())