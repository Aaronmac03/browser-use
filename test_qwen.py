#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv
from runner import make_browser, build_tools_for_subtask
from browser_use import Agent, ChatOpenAI

async def test_qwen():
    load_dotenv()
    
    # Test with Qwen2.5 instead of Mistral
    qwen_llm = ChatOpenAI(
        model="qwen2.5:7b-instruct-q4_k_m",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        timeout=120,
        temperature=0.2,
        max_completion_tokens=4096,
        frequency_penalty=0.2,
        top_p=0.95,
        add_schema_to_system_prompt=True,
        stop=["\n```", "\nAssistant:", "\nObservation:", "\nActions:"],
    )
    
    browser = make_browser()
    
    title = "Navigate to Walmart and search for bananas"
    instructions = "1. Navigate to https://www.walmart.com 2. Use the search bar to search for 'bananas' 3. Confirm search results appear"
    success_crit = "Search results page shows banana products available for purchase"
    
    tools = build_tools_for_subtask(title, instructions, success_crit)
    
    try:
        await browser.start()
        print("Browser started successfully")
        
        agent = Agent(
            task=title,
            llm=qwen_llm,
            tools=tools,
            browser=browser,
            max_failures=2,
            step_timeout=90,
            max_actions_per_step=4,
            use_vision=False,
            use_thinking=True,
            flash_mode=False,
        )
        
        print("Starting Qwen2.5 agent...")
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
    asyncio.run(test_qwen())