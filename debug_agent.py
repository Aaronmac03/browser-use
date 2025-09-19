import asyncio
from dotenv import load_dotenv
from browser_use import Agent, BrowserSession

load_dotenv(dotenv_path=".env")

async def main():
    agent = Agent(
        task="test",
        browser_session=BrowserSession(headless=False)
    )
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())