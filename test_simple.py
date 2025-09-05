#!/usr/bin/env python3

import asyncio
import os
from browser_use import Agent

async def test_simple():
    """Simple test to verify basic browser functionality"""
    
    # Use a clean temporary profile
    os.environ["USE_REAL_CHROME_PROFILE"] = "0"
    os.environ["ENABLE_DEFAULT_EXTENSIONS"] = "0"
    os.environ["BROWSER_START_TIMEOUT_SEC"] = "60"
    
    try:
        agent = Agent(
            task="Navigate to https://httpbin.org/get and tell me what you see",
            llm_provider="llamacpp",
            llm_provider_options={
                "base_url": "http://localhost:8080",
                "model": "qwen2.5:7b-instruct-q4_k_m",
                "temperature": 0.1,
                "timeout": 60
            }
        )
        
        print("Starting agent...")
        result = await agent.run()
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple())