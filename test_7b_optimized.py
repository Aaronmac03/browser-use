#!/usr/bin/env python3
"""
Test optimized 7B model performance for web navigation.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_7b_optimized():
    """Test 7B model with optimized configuration."""
    
    print("🚀 7B Model Optimization Test")
    print("=" * 35)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    print(f"⏱️  Timeout: {local_llm.timeout}s")
    
    # Progressive test cases - start simple, build complexity
    test_cases = [
        {
            "name": "Simple Navigation",
            "task": "Navigate to example.com",
            "timeout": 60,
        },
        {
            "name": "Walmart Homepage",
            "task": "Navigate to walmart.com",
            "timeout": 90,
        },
        {
            "name": "Find Store Locator",
            "task": "Go to walmart.com and find the store locator link",
            "timeout": 120,
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"Task: {test_case['task']}")
        print("-" * 35)
        
        try:
            # Optimized configuration for 7B model
            agent = Agent(
                task=test_case['task'],
                llm=local_llm,
                tools=tools,
                browser=browser,
                # 7B-optimized settings
                use_thinking=True,
                use_vision=False,
                max_actions_per_step=2,      # Small focused steps
                max_history_items=8,         # Minimal context
                step_timeout=test_case['timeout'],
                max_failures=2,              # Allow some retries
                # Enhanced prompting for 7B model
                extend_system_message=f"""
You are a focused web navigation agent. Your task: {test_case['task']}

STRATEGY:
1. Navigate directly to the target site
2. Look for the required elements
3. Take one clear action at a time
4. Call 'done' when successful

Keep actions simple and direct. Don't overthink.
                """,
                include_tool_call_examples=True,
                directly_open_url=True,
            )
            
            print("🚀 Starting test...")
            result = await agent.run()
            
            # Simple success evaluation
            if result and len(result.all_model_outputs) > 0:
                print("✅ COMPLETED - Agent executed actions")
                results.append(("PASS", test_case['name']))
            else:
                print("❌ FAILED - No actions executed")
                results.append(("FAIL", test_case['name']))
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(("ERROR", test_case['name']))
        
        print("-" * 35)
    
    # Summary
    print(f"\n📊 7B Model Performance Summary")
    print("=" * 35)
    passed = sum(1 for status, _ in results if status == "PASS")
    total = len(results)
    
    for status, name in results:
        emoji = "✅" if status == "PASS" else "❌"
        print(f"{emoji} {name}: {status}")
    
    print(f"\n🎯 Score: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed >= 2:
        print("🎉 7B model shows good navigation capability!")
        print("💡 Ready for more complex tasks")
    elif passed >= 1:
        print("⚠️  7B model shows partial capability")
        print("🔧 May need further optimization")
    else:
        print("🔧 7B model needs significant optimization")
    
    # Cleanup
    try:
        await browser.kill()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_7b_optimized())