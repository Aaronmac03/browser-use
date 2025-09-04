#!/usr/bin/env python3
"""
E2E smoke test for browser-use.
Minimal test that starts browser, navigates to example.com, reads title, and quits.
Set RUN_E2E_SMOKE=1 to enable (CI can skip by default).
"""

import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Load environment
load_dotenv()

def log(msg: str, level: str = "INFO"):
    """Simple logging function"""
    print(f"[{level}] {msg}", flush=True)


async def smoke_test():
    """Run a minimal E2E smoke test"""
    
    # Check if smoke test is enabled
    if os.getenv("RUN_E2E_SMOKE", "0") != "1":
        log("Smoke test disabled. Set RUN_E2E_SMOKE=1 to enable.", "INFO")
        return True
    
    log("Starting E2E smoke test...", "INFO")
    
    try:
        # Import browser-use components
        from browser_use import Browser
        from runner import make_browser, ensure_profile_copy_if_requested
        
        # Setup browser configuration
        user_dir, prof = ensure_profile_copy_if_requested()
        log(f"Using profile: {user_dir}/{prof}", "INFO")
        
        # Create browser instance
        log("Creating browser instance...", "INFO")
        browser = make_browser()
        
        # Start browser session
        log("Starting browser session...", "INFO")
        start_time = time.time()
        
        async with browser.new_session() as session:
            startup_time = time.time() - start_time
            log(f"Browser started in {startup_time:.2f}s", "INFO")
            
            # Navigate to example.com
            log("Navigating to example.com...", "INFO")
            nav_start = time.time()
            await session.navigate("https://example.com")
            nav_time = time.time() - nav_start
            log(f"Navigation completed in {nav_time:.2f}s", "INFO")
            
            # Wait a moment for page to load
            await asyncio.sleep(2)
            
            # Get page title
            log("Reading page title...", "INFO")
            title_start = time.time()
            
            # Get the current page info
            page_info = await session.get_page_info()
            title = page_info.get('title', 'No title found')
            url = page_info.get('url', 'No URL found')
            
            title_time = time.time() - title_start
            log(f"Title read in {title_time:.2f}s", "INFO")
            
            # Validate results
            log(f"Page title: '{title}'", "INFO")
            log(f"Page URL: '{url}'", "INFO")
            
            # Basic validation
            if "example" not in title.lower():
                log(f"WARNING: Expected 'example' in title, got: {title}", "WARN")
            
            if "example.com" not in url.lower():
                log(f"WARNING: Expected 'example.com' in URL, got: {url}", "WARN")
            
            total_time = time.time() - start_time
            log(f"Total test time: {total_time:.2f}s", "INFO")
            
            # Test passed
            log("✅ Smoke test PASSED", "SUCCESS")
            return True
            
    except Exception as e:
        log(f"❌ Smoke test FAILED: {e}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        return False


async def main():
    """Main function"""
    try:
        success = await smoke_test()
        return 0 if success else 1
    except Exception as e:
        log(f"Smoke test error: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)