import asyncio
import os
from dotenv import load_dotenv
load_dotenv()  # Load API keys from .env file

# Initialize Laminar tracing
from lmnr import Laminar
Laminar.initialize()

from browser_use import Agent, ChatGoogle, BrowserProfile, BrowserSession

async def main():
    # Create a browser session with keep_alive configuration
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            user_data_dir='C:/Users/drmcn/.config/browseruse/profiles/default',
            keep_alive=True,
            headless=False  # Make sure this is False to see the browser
        )
    )
    
    # Create an agent with a specific task
    agent = Agent(
        task="what is today's high forecast temperature in 40205",
        llm=ChatGoogle(
            model="gemini-2.5-flash",
            api_key=os.getenv('GOOGLE_API_KEY')
        ),
        browser_session=browser_session,
        use_vision=False,  # Explicitly disable vision for models that don't support it
    )

    
    # Run the agent
    await agent.run()
    print("\n✅ Task completed! Browser will stay open.")
    input("Press Enter to close the browser...")
    await browser_session.kill()

if __name__ == '__main__':
    asyncio.run(main())
