#!/usr/bin/env python3
"""
Test improved local LLM performance with optimized prompting.
Focus on simple, reliable navigation patterns.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_improved_local():
    """Test improved local LLM with optimized configuration."""
    
    print("🚀 Improved Local LLM Test")
    print("=" * 30)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    print(f"⏱️  Timeout: {local_llm.timeout}s")
    
    # Simple, focused test cases
    test_cases = [
        {
            "name": "Direct Navigation",
            "task": "Navigate to walmart.com",
            "expected": "Should reach walmart.com homepage",
        },
        {
            "name": "Store Locator Search", 
            "task": "Go to walmart.com and look for a store locator or find store link",
            "expected": "Should find and identify store locator functionality",
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"Task: {test_case['task']}")
        print(f"Expected: {test_case['expected']}")
        print("-" * 30)
        
        try:
            # Optimized agent configuration for local LLM
            agent = Agent(
                task=test_case['task'],
                llm=local_llm,
                tools=tools,
                browser=browser,
                # Optimized settings for reliability
                use_thinking=True,
                use_vision=False,
                max_actions_per_step=2,      # Keep steps small and focused
                max_history_items=8,         # Minimal context for speed
                step_timeout=90,             # Reasonable timeout for 7B model
                max_failures=2,              # Allow some retries
                # Focused prompting
                extend_system_message=f"""
You are a web navigation specialist. Task: {test_case['task']}

APPROACH:
1. Navigate directly to the target site
2. Look for the required element/functionality  
3. Take one clear action at a time
4. Call 'done' when you find what you're looking for

Be direct and efficient. Don't explore unnecessarily.
                """,
                include_tool_call_examples=True,
                directly_open_url=True,
            )
            
            print("🚀 Starting test...")
            result = await agent.run()
            
            # Evaluate success based on actions taken
            if result and len(result.all_model_outputs) > 0:
                # Check if agent took meaningful actions
                actions_taken = len([step for step in result.all_model_outputs if step.actions])
                if actions_taken > 0:
                    print(f"✅ COMPLETED - {actions_taken} action steps taken")
                    results.append(("PASS", test_case['name']))
                else:
                    print("❌ FAILED - No meaningful actions taken")
                    results.append(("FAIL", test_case['name']))
            else:
                print("❌ FAILED - No result returned")
                results.append(("FAIL", test_case['name']))
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(("ERROR", test_case['name']))
        
        print("-" * 30)
    
    # Summary
    print(f"\n📊 Local LLM Performance Summary")
    print("=" * 30)
    passed = sum(1 for status, _ in results if status == "PASS")
    total = len(results)
    
    for status, name in results:
        emoji = "✅" if status == "PASS" else "❌"
        print(f"{emoji} {name}: {status}")
    
    print(f"\n🎯 Success Rate: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 Excellent! Local LLM is performing well")
        print("💡 Ready for complex multi-step tasks")
    elif passed >= total * 0.5:
        print("⚠️  Good progress, some optimization needed")
        print("🔧 Consider further prompt refinement")
    else:
        print("🔧 Significant optimization needed")
        print("💭 May need different model or approach")
    
    # Cleanup
    try:
        await browser.kill()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_improved_local())