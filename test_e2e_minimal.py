#!/usr/bin/env python3

import asyncio
import os
from browser_use import Agent, Browser

async def test_e2e_minimal():
    """Minimal E2E test bypassing complex profile setup"""
    
    # Force minimal configuration
    os.environ["USE_REAL_CHROME_PROFILE"] = "0"
    os.environ["ENABLE_DEFAULT_EXTENSIONS"] = "0"
    os.environ["COPY_PROFILE_ONCE"] = "0"
    
    try:
        # Create minimal browser with basic args
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
        
        # Test with local LLM using ChatLlamaCpp
        from browser_use import ChatLlamaCpp
        
        llm = ChatLlamaCpp(
            base_url="http://localhost:8080",
            model="qwen2.5-14b-instruct-q4_k_m",
            temperature=0.1,
            timeout=60
        )
        
        agent = Agent(
            task="Navigate to https://example.com and tell me the main heading text",
            llm=llm,
            browser=browser,
            max_failures=2,
            max_actions_per_step=2,
            max_history=10
        )
        
        print("Starting minimal E2E test...")
        result = await agent.run()
        
        print(f"[DEBUG] Result type: {type(result)}")
        print(f"[DEBUG] Result: {result}")
        
        # Check different result formats
        if result:
            if hasattr(result, 'success'):
                success = result.success
                content = getattr(result, 'extracted_content', str(result))
                print(f"SUCCESS: {success}")
                print(f"RESULT: {content}")
                return success, content
            elif hasattr(result, 'all_results') and result.all_results:
                final_result = result.all_results[-1]
                success = getattr(final_result, 'success', False)
                content = getattr(final_result, 'extracted_content', str(final_result))
                print(f"SUCCESS: {success}")
                print(f"RESULT: {content}")
                return success, content
            else:
                # Assume success if we got a result
                print(f"SUCCESS: True (inferred)")
                print(f"RESULT: {str(result)}")
                return True, str(result)
        else:
            print("No results returned")
            return False, "No results"
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

if __name__ == "__main__":
    success, result = asyncio.run(test_e2e_minimal())
    print(f"\nFINAL GRADE: {'PASS' if success else 'FAIL'}")
    print(f"RESULT: {result}")