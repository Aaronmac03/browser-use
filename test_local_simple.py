#!/usr/bin/env python3
"""
Simple test for local LLM navigation capabilities.
Focus: Test basic web navigation without complex e2e flows.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm, make_browser, build_tools
from browser_use import Agent

async def test_simple_navigation():
    """Test basic navigation capabilities with local LLM only."""
    
    print("🧪 Testing Local LLM Navigation Capabilities")
    print("=" * 50)
    
    # Setup
    local_llm = make_local_llm()
    browser = make_browser()
    tools = build_tools()
    
    print(f"🤖 Model: {local_llm.model}")
    print(f"🌐 Browser: Ready")
    
    # Simple test cases in order of complexity
    test_cases = [
        {
            "name": "Basic Navigation",
            "task": "Navigate to google.com and verify you can see the search box",
            "expected": "Should successfully navigate and identify search elements"
        },
        {
            "name": "Simple Search",
            "task": "Go to google.com and search for 'walmart store locator'",
            "expected": "Should perform search and see results"
        },
        {
            "name": "Link Following", 
            "task": "Search for 'walmart store locator' on Google and click the first walmart.com result",
            "expected": "Should navigate from search results to walmart.com"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"Task: {test_case['task']}")
        print(f"Expected: {test_case['expected']}")
        print("-" * 40)
        
        try:
            # Configure agent for local LLM optimization
            agent = Agent(
                task=test_case['task'],
                llm=local_llm,
                tools=tools,
                browser=browser,
                # Optimized settings for local LLM
                use_thinking=True,  # Enable reasoning for 14B model
                use_vision=False,   # Disable for performance
                max_actions_per_step=3,  # Keep steps focused
                max_history_items=10,    # Smaller context
                step_timeout=120,        # Reasonable timeout
                max_failures=1,          # Fail fast for simple tests
                # Enhanced prompting for local model
                extend_system_message="""
You are a focused web navigation agent. Work step by step:
1. Navigate to the target site
2. Identify the required elements clearly
3. Perform the requested action
4. Verify success before completing

Be precise with element selection. If an action fails, try a different approach immediately.
Complete the task efficiently and call 'done' when successful.
                """,
                include_tool_call_examples=True,
                directly_open_url=True,
            )
            
            print("🚀 Starting agent...")
            result = await agent.run()
            
            # Evaluate result
            # Check if result has the expected structure
            if hasattr(result, 'all_results'):
                success = any(r.success for r in result.all_results if r.success is not None)
            else:
                # Fallback for different result structure
                success = hasattr(result, 'success') and result.success
                
            if success:
                print("✅ PASSED")
                results.append(("PASS", test_case['name']))
            else:
                print("❌ FAILED - Task not completed successfully")
                results.append(("FAIL", test_case['name']))
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(("ERROR", test_case['name']))
        
        print("-" * 40)
    
    # Summary
    print(f"\n📊 Test Results Summary")
    print("=" * 50)
    passed = sum(1 for status, _ in results if status == "PASS")
    total = len(results)
    
    for status, name in results:
        emoji = "✅" if status == "PASS" else "❌"
        print(f"{emoji} {name}: {status}")
    
    print(f"\n🎯 Score: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Local LLM navigation is working well.")
    elif passed > total // 2:
        print("⚠️  Partial success. Local LLM needs some optimization.")
    else:
        print("🔧 Local LLM needs significant improvement for web navigation.")
    
    # Cleanup
    try:
        await browser.kill()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_simple_navigation())