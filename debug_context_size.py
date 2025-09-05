#!/usr/bin/env python3
"""Debug context size being sent to local LLM."""

import asyncio
from browser_use import Agent, Browser
from browser_use.llm.llamacpp.chat import ChatLlamaCpp
from browser_use.llm.messages import UserMessage, SystemMessage

async def debug_context_size():
    """Debug what content is being sent to local LLM."""
    
    # Create local LLM
    local_llm = ChatLlamaCpp(
        base_url="http://localhost:8080",
        model="qwen2.5-7b-instruct-q4_k_m.gguf",
        temperature=0.1,
        timeout=60
    )
    
    # Test system prompt size
    print("Testing system prompt size...")
    browser = Browser()
    
    try:
        agent = Agent(
            task="Navigate to example.com",
            llm=local_llm,
            browser=browser,
            use_vision=False,
            max_actions_per_step=1,
            max_history_items=6,
            max_clickable_elements_length=100,  # Extremely small limit
            step_timeout=10  # Short timeout for testing
        )
        
        # Get the system message from the agent
        system_msg = agent._message_manager.system_prompt
        print(f"System prompt length: {len(system_msg.content)} characters")
        print(f"System prompt preview: {system_msg.content[:200]}...")
        
        # Test with just system message
        messages = [system_msg]
        print(f"Testing system message only...")
        response = await local_llm.ainvoke(messages)
        print(f"System message test successful: {response.completion[:100]}...")
        
    except Exception as e:
        print(f"System message test failed: {e}")
    finally:
        # Proper cleanup
        if hasattr(browser, 'session') and browser.session:
            await browser.session.close()

if __name__ == "__main__":
    asyncio.run(debug_context_size())