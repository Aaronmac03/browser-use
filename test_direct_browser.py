#!/usr/bin/env python3

import asyncio
import os
from browser_use import Browser

async def test_direct_browser():
    """Test direct browser creation like test_e2e_minimal.py"""
    
    # Force minimal configuration
    os.environ["USE_REAL_CHROME_PROFILE"] = "0"
    os.environ["ENABLE_DEFAULT_EXTENSIONS"] = "0"
    os.environ["COPY_PROFILE_ONCE"] = "0"
    
    try:
        print("Creating browser with direct approach...")
        
        # Create minimal browser with basic args (same as test_e2e_minimal.py)
        browser = Browser(
            executable_path=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            headless=False,
            devtools=False,
            keep_alive=True,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
                "--disable-gpu-sandbox",
                "--disable-sync",
                "--disable-translate",
                "--disable-default-apps",
            ]
        )
        
        print("Browser created successfully!")
        print("Testing browser startup...")
        
        # Try to start the browser
        await browser.start()
        print("Browser started successfully!")
        
        # Try to navigate to a simple page
        await browser.navigate_to("https://example.com")
        title = await browser.get_current_page_title()
        print(f"Successfully navigated to example.com, title: {title}")
        
        await browser.stop()
        print("Browser stopped successfully!")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_direct_browser())
    print(f"\nFINAL RESULT: {'PASS' if success else 'FAIL'}")