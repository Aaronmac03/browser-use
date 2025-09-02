#!/usr/bin/env python3

import asyncio
from dotenv import load_dotenv
from runner import make_browser, make_local_llm, build_tools_for_subtask
from browser_use import Agent

async def test_simple():
    load_dotenv()
    
    # Test just the first subtask with a simpler approach
    browser = make_browser()
    local_llm = make_local_llm()
    
    title = "Navigate to Walmart.com"
    instructions = "Simply navigate to https://www.walmart.com and confirm the page loads"
    success_crit = "The page shows Walmart branding and the main navigation"
    
    tools = build_tools_for_subtask(title, instructions, success_crit)
    
    try:
        await browser.start()
        print("Browser started successfully")
        
        agent = Agent(
            task=title,
            llm=local_llm,
            tools=tools,
            browser=browser,
            max_failures=2,
            step_timeout=60,
            max_actions_per_step=3,
            use_vision=False,
            flash_mode=False,
        )
        
        print("Starting agent...")
        result = await agent.run()
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await browser.kill()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_simple())