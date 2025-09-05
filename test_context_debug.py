#!/usr/bin/env python3
"""Test with debug logging to see actual context size."""

import asyncio
import logging
from browser_use import Agent, Browser
from browser_use.llm.llamacpp.chat import ChatLlamaCpp

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_with_debug():
    """Test with debug logging enabled."""
    
    # Create local LLM
    local_llm = ChatLlamaCpp(
        base_url="http://localhost:8080",
        model="qwen2.5-7b-instruct-q4_k_m.gguf",
        temperature=0.1,
        timeout=60
    )
    
    # Create browser and agent with ultra-small limits
    browser = Browser()
    
    try:
        agent = Agent(
            task="Navigate to example.com",
            llm=local_llm,
            browser=browser,
            use_vision=False,
            max_actions_per_step=1,
            max_history_items=6,
            max_clickable_elements_length=100,  # Ultra small
            step_timeout=15  # Short timeout
        )
        
        print("Starting agent run...")
        result = await agent.run()
        print(f"Agent completed: {result}")
        
    except Exception as e:
        print(f"Agent failed: {e}")
    finally:
        # Proper cleanup
        if hasattr(browser, 'session') and browser.session:
            await browser.session.close()

if __name__ == "__main__":
    asyncio.run(test_with_debug())