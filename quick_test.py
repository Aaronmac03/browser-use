"""
Quick test to demonstrate working browser-use agent
"""

import asyncio
import os
from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle
from dotenv import load_dotenv

load_dotenv()

async def quick_test():
    print("🤖 Running quick browser automation test...")
    
    # Simple browser session
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            headless=False,
            keep_alive=False
        )
    )
    
    # Use Gemini for execution
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    # Simple task
    agent = Agent(
        task="Go to Google.com and search for 'browser automation'",
        llm=llm,
        browser_session=browser_session,
        max_steps=5
    )
    
    try:
        print("🚀 Starting browser automation...")
        history = await agent.run()
        result = history.final_result()
        print(f"✅ Success! Result: {result}")
        await browser_session.kill()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        await browser_session.kill()
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    print(f"🎯 Test {'PASSED' if success else 'FAILED'}!")