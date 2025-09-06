#!/usr/bin/env python3

import asyncio
import os
from browser_use import Agent, Browser
from browser_use.llm.llamacpp import ChatLlamaCpp

async def test_e2e_final():
    """Final E2E test with proper local LLM configuration"""
    
    # Force minimal configuration
    os.environ["USE_REAL_CHROME_PROFILE"] = "0"
    os.environ["ENABLE_DEFAULT_EXTENSIONS"] = "0"
    os.environ["COPY_PROFILE_ONCE"] = "0"
    
    try:
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
        
        # Create local LLM directly
        local_llm = ChatLlamaCpp(
            model="qwen2.5:7b-instruct-q4_k_m",
            base_url="http://localhost:8080",
            timeout=60,
            temperature=0.1,
            max_tokens=4096,
        )
        
        # Test with local LLM
        agent = Agent(
            task="Navigate to https://example.com and tell me the main heading text",
            llm=local_llm,
            browser=browser,
            max_failures=2,
            max_actions_per_step=2,
            max_history=10
        )
        
        print("Starting E2E test with local LLM...")
        result = await agent.run()
        
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
        
        # Check if task completed successfully
        # Handle AgentHistoryList result
        if hasattr(result, 'all_results') and result.all_results:
            final_result = result.all_results[-1]  # Get last result
            success = getattr(final_result, 'success', None)
            content = getattr(final_result, 'extracted_content', 'No content')
            print(f"SUCCESS: {success}")
            print(f"RESULT: {content}")
            return success, content
        else:
            print("No results returned")
            return False, "No results"
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

if __name__ == "__main__":
    success, result = asyncio.run(test_e2e_final())
    print(f"\nFINAL GRADE: {'PASS' if success else 'FAIL'}")
    print(f"RESULT: {result}")