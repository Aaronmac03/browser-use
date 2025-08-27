import asyncio
from dotenv import load_dotenv
load_dotenv()  # Load API keys from .env file

from browser_use import Agent, ChatOpenAI, BrowserProfile, BrowserSession

async def main():
    # Create a browser profile pointing to the dedicated directory
    browser_profile = BrowserProfile(
        user_data_dir='C:/Users/drmcn/.config/browseruse/profiles/default',
    )
    
    # Create a browser session with this profile
    browser_session = BrowserSession(browser_profile=browser_profile)
    
    # Create an agent with a specific task
    agent = Agent(
        task="Search for 'what is browser automation' and summarize the top 3 results",
        llm=ChatOpenAI(model="gpt-4.1-mini"),  # You can change the model if needed
        browser_session=browser_session,
    )
    
    # Run the agent
    await agent.run()

if __name__ == '__main__':
    asyncio.run(main())
