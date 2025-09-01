#!/usr/bin/env python3

import asyncio
import sys
from browser_use import Agent, Browser, ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

async def simple_test():
    # Use cloud model for this simple test
    llm = ChatOpenAI(model="o3-mini")  # Faster and cheaper than o3
    
    # Use the copied profile since it worked
    browser = Browser(
        user_data_dir="./runtime/user_data",
        profile_directory="Default", 
        headless=False
    )
    
    agent = Agent(
        task="Navigate to Google.com and search for 'browser-use python' and take a screenshot",
        llm=llm,
        browser=browser,
        max_failures=3,
        step_timeout=60  # Shorter timeout for quick test
    )
    
    print("🚀 Starting simple test...")
    result = await agent.run()
    print(f"✅ Test completed: {result}")
    
    return result

if __name__ == "__main__":
    asyncio.run(simple_test())