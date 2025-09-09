#!/usr/bin/env python3
"""Test local LLM context size to debug 502 errors."""

import asyncio
from browser_use import Agent, Browser
from browser_use.llm.llamacpp.chat import ChatLlamaCpp

async def test_local_llm_context():
    """Test what content is being sent to local LLM."""
    
    # Create local LLM
    local_llm = ChatLlamaCpp(
        base_url="http://localhost:8080",
        model="qwen2.5-14b-instruct-q4_k_m.gguf",
        temperature=0.1,
        timeout=60
    )
    
    # Test simple request first
    print("Testing simple LLM request...")
    try:
        from browser_use.llm.messages import UserMessage
        messages = [UserMessage(content="What is 2+2?")]
        response = await local_llm.ainvoke(messages)
        print(f"Simple request successful: {response.completion[:100]}...")
    except Exception as e:
        print(f"Simple request failed: {e}")
        return
    
    # Create browser and agent with very small DOM limit
    print("\nTesting browser automation with minimal DOM...")
    browser = Browser()
    
    agent = Agent(
        task="Navigate to example.com",
        llm=local_llm,
        browser=browser,
        use_vision=False,
        max_actions_per_step=1,
        max_history_items=6,
        max_clickable_elements_length=500,  # Very small limit
        step_timeout=30
    )
    
    try:
        result = await agent.run()
        print(f"Agent run successful: {result}")
    except Exception as e:
        print(f"Agent run failed: {e}")
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_local_llm_context())