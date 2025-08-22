import asyncio, os
from dotenv import load_dotenv
load_dotenv()

# Laminar tracing (uses LMNR_PROJECT_API_KEY from env if not passed)
from lmnr import Laminar
Laminar.initialize()

from browser_use import Agent, BrowserSession
from browser_use.llm import ChatGoogle
from browser_use.browser import BrowserProfile

async def main():
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            user_data_dir=os.path.expanduser(r"C:/Users/drmcn/.config/browseruse/profiles/default"),
            keep_alive=True,
            headless=False,
        )
    )

    agent = Agent(
        task="What's today's forecast high temperature for ZIP 40205?",
        llm=ChatGoogle(model="gemini-2.5-flash"),  # or 'gemini-2.0-flash-exp'
        browser_session=browser_session,
        use_vision=False,          # conditional vision can be added later
        max_actions_per_step=8,    # good capability/cost balance
        max_failures=3,            # optional: sturdier retries
        retry_delay=10,            # optional: backoff on rate limits
        save_conversation_path="logs/conversation",  # optional: debugging trace
    )

    history = await agent.run(max_steps=60)
    print("\nFinal result:\n", history.final_result())
    input("Press Enter to close the browser...")
    await browser_session.kill()

if __name__ == "__main__":
    asyncio.run(main())
