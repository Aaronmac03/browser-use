#!/usr/bin/env python3
"""
Focused test for local LLM web navigation.
Tests specific navigation patterns that were failing.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_focused_navigation():
    """Test specific navigation issues with local LLM."""
    
    print("🎯 Focused Local LLM Navigation Test")
    print("=" * 40)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    
    # Single focused test - navigate to Walmart directly
    task = "Navigate to walmart.com and find the store locator"
    
    print(f"📋 Task: {task}")
    print("-" * 40)
    
    try:
        # Optimized agent configuration for local LLM
        agent = Agent(
            task=task,
            llm=local_llm,
            tools=tools,
            browser=browser,
            # Conservative settings for reliability
            use_thinking=True,
            use_vision=False,
            max_actions_per_step=2,  # Keep steps small
            max_history_items=8,     # Small context
            step_timeout=180,        # Longer timeout for 14B model
            max_failures=1,          # Fail fast
            # Clear, focused prompting
            extend_system_message="""
You are a web navigation specialist. Your task is simple:

1. Navigate to walmart.com
2. Look for a "Store Locator" or "Find a Store" link/button
3. Click on it
4. Call 'done' when you reach the store locator page

Be direct and efficient. Don't overthink it.
If you see the store locator page, call 'done' immediately.
            """,
            include_tool_call_examples=True,
            directly_open_url=True,
        )
        
        print("🚀 Starting focused test...")
        result = await agent.run()
        
        print("📊 Test completed")
        print(f"Result type: {type(result)}")
        
        # Simple success check - did we complete without major errors?
        if result:
            print("✅ Agent completed execution")
            print("🎯 Check browser manually to see if store locator was reached")
        else:
            print("❌ Agent failed to complete")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print("\n🔍 Analysis:")
    print("- Check if the agent navigated to walmart.com")
    print("- Check if it found and clicked store locator")
    print("- Look for repetitive actions or getting stuck")
    print("- Note any CDP errors or element interaction issues")
    
    # Keep browser open for manual inspection
    print("\n⏸️  Browser left open for manual inspection")
    print("Press Ctrl+C to close when done reviewing")
    
    try:
        # Keep the script running so browser stays open
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🧹 Cleaning up...")
        try:
            await browser.kill()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_focused_navigation())