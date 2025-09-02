#!/usr/bin/env python3
"""
Minimal test to validate local LLM basic functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser
from browser_use import Agent

async def test_minimal():
    """Minimal test - just navigate to a simple page."""
    
    print("🧪 Minimal Local LLM Test")
    print("=" * 30)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    
    print(f"🤖 Model: {local_llm.model}")
    
    # Simplest possible task
    task = "Navigate to example.com"
    
    print(f"📋 Task: {task}")
    print("-" * 30)
    
    try:
        # Minimal agent configuration
        agent = Agent(
            task=task,
            llm=local_llm,
            browser=browser,
            # Minimal settings
            use_thinking=False,      # Disable thinking to reduce complexity
            use_vision=False,
            max_actions_per_step=1,  # One action at a time
            max_history_items=6,     # Minimum allowed
            step_timeout=60,         # Short timeout
            max_failures=1,
            # Very simple prompting
            extend_system_message="Navigate to example.com and call 'done' when you see the page.",
            directly_open_url=True,
        )
        
        print("🚀 Starting minimal test...")
        result = await agent.run()
        
        print("✅ Test completed successfully")
        print(f"Result: {type(result)}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Cleanup
    try:
        await browser.kill()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_minimal())