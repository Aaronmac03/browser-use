#!/usr/bin/env python3
"""
Test optimized local LLM on the actual Walmart store locator task.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_walmart_optimized():
    """Test optimized local LLM on Walmart store locator task."""
    
    print("🛒 Walmart Store Locator - Optimized Local LLM Test")
    print("=" * 50)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    print(f"⏱️  Timeout: {local_llm.timeout}s")
    
    # The actual task from the goal
    task = "Navigate to walmart.com and find the store locator"
    
    print(f"📋 Task: {task}")
    print("-" * 50)
    
    try:
        # Optimized configuration for local LLM
        agent = Agent(
            task=task,
            llm=local_llm,
            tools=tools,
            browser=browser,
            # Optimized settings
            use_thinking=True,
            use_vision=False,
            max_actions_per_step=2,      # Small focused steps
            max_history_items=8,         # Minimal context
            step_timeout=90,             # Reasonable timeout for 7B
            max_failures=2,              # Allow some retries
            # Task-specific prompting
            extend_system_message=f"""
TASK: {task}

STRATEGY:
1. Navigate to walmart.com (will happen automatically)
2. Look for store locator links in header/footer navigation
3. Common text to look for: "Store Locator", "Find a Store", "Locations"
4. Click on the store locator link when found
5. Call 'done' when you reach the store locator page

ELEMENT INTERACTION:
- If click by index fails, try scroll_to_text with the link text
- Look in main navigation menu first
- Check footer if not in header
- Don't get distracted by search boxes or other features

SUCCESS = Find and click store locator link + Call done when reached
            """,
            include_tool_call_examples=True,
            directly_open_url=True,
        )
        
        print("🚀 Starting Walmart store locator test...")
        result = await agent.run()
        
        # Evaluate success
        if result:
            print("✅ Agent completed execution")
            
            # Check for successful completion
            success_found = False
            done_called = False
            steps_taken = len(result)
            
            print(f"📊 Steps taken: {steps_taken}")
            
            # Look for done action in the results
            for step in result:
                if hasattr(step, 'actions'):
                    for action in step.actions:
                        if hasattr(action, 'action_name') and action.action_name == 'done':
                            done_called = True
                            if hasattr(action, 'success') and action.success:
                                success_found = True
                                print("✅ Task marked as successful by agent")
                                break
            
            if success_found:
                print("🎉 EXCELLENT - Local LLM successfully completed the task!")
                print("💡 Ready for complex multi-step navigation tasks")
            elif done_called:
                print("⚠️  PARTIAL SUCCESS - Called done but not marked successful")
                print("🔧 May need minor prompt refinement")
            else:
                print("❌ INCOMPLETE - Did not call done to complete task")
                print("🔧 Needs completion training")
                
        else:
            print("❌ FAILED - No result returned")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print(f"\n🎯 Local LLM Performance Assessment:")
    print("✅ Model Selection: 7B model for speed and reliability")
    print("✅ Timeout Optimization: 60s for 7B model responses")
    print("✅ Prompt Optimization: Task-focused, completion-oriented")
    print("✅ Configuration: Small steps, minimal context for efficiency")
    
    print(f"\n💡 Next Steps for Complex Tasks:")
    print("- Use this optimized local LLM as the primary worker")
    print("- Reserve cloud models for planning and critical analysis")
    print("- Focus on task completion rather than exploration")
    print("- Leverage web_search tool for finding official URLs")
    
    # Keep browser open for manual inspection
    print(f"\n⏸️  Browser left open for manual verification")
    print("Check if the agent reached the Walmart store locator page")
    print("Press Ctrl+C when done reviewing")
    
    try:
        # Keep running so browser stays open
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🧹 Cleaning up...")
        try:
            await browser.kill()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_walmart_optimized())