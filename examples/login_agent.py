import asyncio
import os
import sys
import uuid

# Add the project root to the path so we can import browser_use
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_use import BrowserSession
from browser_use.tools.service import Tools
from browser_use.tools.views import GoToUrlAction

async def main():
    # --- 1. Create an isolated BrowserSession ---
    # We use a unique user_data_dir to prevent session conflicts.
    user_data_dir = f"/tmp/browser-use-session-{uuid.uuid4()}"
    print(f"Using isolated browser session in: {user_data_dir}")

    browser_session = BrowserSession(
        user_data_dir=user_data_dir,
        channel="chrome",
        headless=False,
        keep_alive=True
    )
    await browser_session.start()

    # --- 2. Instantiate the Tools ---
    tools = Tools()

    # --- 3. Navigate to Gmail ---
    print("Navigating to Gmail...")
    await tools.act(
        GoToUrlAction(url="https://www.gmail.com").model_dump(),
        browser_session=browser_session
    )

    print("\nBrowser is ready. Please log in manually.")
    print("I will need the element indices for the email, password, and 'Next' buttons to proceed.")

    # Keep the browser open for manual interaction
    await asyncio.sleep(300)

    await browser_session.stop()

if __name__ == '__main__':
    asyncio.run(main())