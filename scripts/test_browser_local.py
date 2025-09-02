#!/usr/bin/env python3
import asyncio
import os
from dotenv import load_dotenv

from browser_use import Agent, Tools
from runner import make_local_llm, make_browser


async def main():
    load_dotenv()

    # Use a fresh local profile dir to avoid copying the system profile during a quick test
    os.environ.setdefault("COPY_PROFILE_ONCE", "0")
    os.environ.setdefault("CHROME_USER_DATA_DIR", "./runtime/test_user_data")
    os.environ.setdefault("CHROME_PROFILE_DIRECTORY", "Default")

    llm = make_local_llm()
    browser = make_browser()

    try:
        await browser.start()

        tools = Tools()  # default toolset with standard 'done'

        task = (
            "Open https://example.com, confirm the H1 text contains 'Example Domain', "
            "then finish with a short summary including the page title."
        )

        agent = Agent(
            task=task,
            llm=llm,
            tools=tools,
            browser=browser,
            use_thinking=False,
            use_vision=False,
            max_failures=2,
            step_timeout=90,
            max_actions_per_step=4,
            directly_open_url=True,
        )

        print("Starting local browser test...")
        result = await agent.run()
        print("\n=== RESULT ===\n", result)

    finally:
        try:
            await browser.kill()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

