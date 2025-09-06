#!/usr/bin/env python3
"""
Test real browser automation to see where the 502 errors occur
"""

import asyncio
import sys
import json
import os
from pathlib import Path

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_minimal_browser_automation():
    """Test minimal browser automation to isolate the issue"""
    
    print("🔧 Testing minimal browser automation...")
    
    try:
        from browser_use import Agent, Browser
        
        # Force minimal configuration
        os.environ["USE_REAL_CHROME_PROFILE"] = "0"
        os.environ["ENABLE_DEFAULT_EXTENSIONS"] = "0"
        os.environ["COPY_PROFILE_ONCE"] = "0"
        
        # Create minimal browser
        browser = Browser(
            executable_path=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            headless=False,
            devtools=False,
            keep_alive=True,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
                "--disable-gpu-sandbox",
                "--disable-sync",
                "--disable-translate",
                "--disable-default-apps",
            ]
        )
        
        # Test with local LLM
        agent = Agent(
            task="Navigate to https://httpbin.org/html and tell me what you see",
            llm_provider="llamacpp",
            llm_provider_options={
                "base_url": "http://localhost:8080",
                "model": "qwen2.5:7b-instruct-q4_k_m",
                "temperature": 0.1,
                "timeout": 60
            },
            browser=browser,
            max_failures=1,  # Reduce to see failures faster
            max_actions_per_step=1,
            max_history=5
        )
        
        print("Starting browser automation test...")
        
        # Capture any errors during execution
        try:
            result = await agent.run()
            print(f"✅ Agent completed successfully")
            print(f"Result type: {type(result)}")
            if hasattr(result, 'all_results'):
                print(f"All results: {len(result.all_results) if result.all_results else 0}")
            return True
            
        except Exception as e:
            print(f"❌ Agent execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_with_browser_context():
    """Test LLM with browser-like context to see if size is the issue"""
    
    print("\n🔧 Testing LLM with large browser context...")
    
    try:
        from runner import make_local_llm
        from browser_use.llm.messages import SystemMessage, UserMessage
        
        llm = make_local_llm()
        
        # Simulate a large DOM context like browser automation would send
        large_dom = """
        <html>
        <head><title>Test Page</title></head>
        <body>
        """ + "<div>Content block</div>\n" * 500 + """
        <h1>Main Heading</h1>
        <p>This is a test page with lots of content.</p>
        </body>
        </html>
        """
        
        system_prompt = """You are a web automation agent. You can navigate websites and interact with elements.

Available actions:
- go_to_url: Navigate to a URL
- click: Click on an element
- type: Type text into an element
- done: Complete the task

Respond with JSON in this format:
{
  "thinking": "your reasoning",
  "evaluation_previous_goal": "assessment",
  "memory": "important info",
  "next_goal": "what's next",
  "action": [{"type": "action_name", "param": "value"}]
}"""
        
        user_prompt = f"""Current page DOM:
{large_dom}

Task: Find the main heading text on this page and report it.

Please analyze the page and provide your next action."""
        
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=user_prompt)
        ]
        
        total_chars = sum(len(m.content) for m in messages)
        print(f"Total context size: {total_chars} characters")
        
        print("Sending large context request...")
        result = await llm.ainvoke(messages)
        
        print(f"✅ LLM handled large context successfully")
        print(f"Response length: {len(result.completion)} chars")
        print(f"Response preview: {result.completion[:200]}...")
        
        # Try to parse as JSON
        try:
            parsed = json.loads(result.completion)
            print("✅ Response is valid JSON")
            return True
        except json.JSONDecodeError:
            print("⚠️ Response is not valid JSON but LLM didn't fail")
            return True
            
    except Exception as e:
        print(f"❌ Large context test failed: {e}")
        if "502" in str(e):
            print("🔍 FOUND 502 ERROR - This is the issue!")
        return False

async def main():
    print("🧪 REAL BROWSER AUTOMATION TEST")
    print("="*60)
    print("Testing to find the root cause of 502 errors")
    print("")
    
    # Test 1: Large context with LLM only
    large_context_success = await test_llm_with_browser_context()
    
    # Test 2: Minimal browser automation
    if large_context_success:
        print("\n" + "="*40)
        browser_success = await test_minimal_browser_automation()
    else:
        print("\n⚠️ Skipping browser test due to LLM context issues")
        browser_success = False
    
    print("\n" + "="*60)
    print("🎯 TEST RESULTS")
    print("="*60)
    
    print(f"Large context LLM: {'✅ PASS' if large_context_success else '❌ FAIL'}")
    print(f"Browser automation: {'✅ PASS' if browser_success else '❌ FAIL'}")
    
    if not large_context_success:
        print("\n🔧 DIAGNOSIS:")
        print("❌ Issue is with large context handling in LLM")
        print("❌ Browser automation fails because DOM content is too large")
        print("❌ Need to implement better context size management")
    elif not browser_success:
        print("\n🔧 DIAGNOSIS:")
        print("❌ Issue is in browser automation layer, not LLM")
        print("❌ Need to investigate browser-use integration")
    else:
        print("\n✅ Both tests passed - issue may be intermittent or fixed")
    
    return large_context_success and browser_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)