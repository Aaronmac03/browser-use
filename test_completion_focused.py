#!/usr/bin/env python3
"""
Test focused on task completion with local LLM.
Emphasizes calling 'done' when goals are achieved.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_completion_focused():
    """Test local LLM with emphasis on task completion."""
    
    print("🎯 Task Completion Focused Test")
    print("=" * 35)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    
    # Very simple task with clear completion criteria
    task = "Navigate to example.com and confirm you can see the page"
    
    print(f"📋 Task: {task}")
    print("-" * 35)
    
    try:
        # Completion-focused configuration
        agent = Agent(
            task=task,
            llm=local_llm,
            tools=tools,
            browser=browser,
            # Settings optimized for completion
            use_thinking=True,
            use_vision=False,
            max_actions_per_step=1,      # One action at a time
            max_history_items=6,         # Minimal context
            step_timeout=60,             # Quick timeout
            max_failures=1,              # Fail fast
            # Completion-focused prompting
            extend_system_message=f"""
TASK: {task}

COMPLETION STRATEGY:
1. Navigate to example.com
2. Verify the page loads (you'll see "Example Domain" heading)
3. IMMEDIATELY call 'done' with success=True

CRITICAL: Call 'done' as soon as you see the example.com page load.
Do NOT explore, click links, or take additional actions.
Your job is to navigate and confirm - that's it.

SUCCESS = Navigate to example.com + Call done
            """,
            include_tool_call_examples=True,
            directly_open_url=True,
        )
        
        print("🚀 Starting completion test...")
        result = await agent.run()
        
        # Check if task was marked as successful
        if result:
            # Look for successful completion in the result
            success_found = False
            done_called = False
            
            # Check the last few steps for 'done' action
            for step in result:
                if hasattr(step, 'actions'):
                    for action in step.actions:
                        if hasattr(action, 'action_name') and action.action_name == 'done':
                            done_called = True
                            if hasattr(action, 'success') and action.success:
                                success_found = True
                                break
            
            if success_found:
                print("✅ EXCELLENT - Task completed successfully with done(success=True)")
            elif done_called:
                print("⚠️  PARTIAL - Called done but not marked as successful")
            else:
                print("❌ FAILED - Never called done to complete the task")
        else:
            print("❌ FAILED - No result returned")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print("\n🔍 Key Insights:")
    print("- Local LLM needs clear completion signals")
    print("- 'done' action is critical for task success")
    print("- Simple tasks should complete in 1-3 steps")
    print("- Avoid over-exploration and unnecessary actions")
    
    # Cleanup
    try:
        await browser.kill()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_completion_focused())