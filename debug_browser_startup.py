#!/usr/bin/env python3
"""
Debug Browser Startup Issues
============================

Isolated test to diagnose browser startup problems.
"""

import asyncio
import subprocess
import time
import aiohttp
import psutil
from pathlib import Path

def log(message: str):
    """Log with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

async def test_chrome_direct_launch():
    """Test launching Chrome directly with minimal args."""
    log("🧪 Testing direct Chrome launch...")
    
    chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    debug_port = 9223
    user_data_dir = r"E:\ai\browser-use\debug_chrome_data"
    
    # Ensure user data dir exists
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    
    # Minimal Chrome args for testing
    args = [
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
        "--disable-web-security",
        "--disable-features=VizDisplayCompositor",
        "--headless=new"
    ]
    
    log(f"Launching Chrome with {len(args)-1} arguments...")
    log(f"Debug port: {debug_port}")
    log(f"User data dir: {user_data_dir}")
    
    try:
        # Launch Chrome
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        log(f"Chrome process started with PID: {process.pid}")
        
        # Wait for Chrome to start
        await asyncio.sleep(3)
        
        # Test CDP connection
        log("Testing CDP connection...")
        
        for attempt in range(10):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'http://localhost:{debug_port}/json/version', timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            log(f"✅ CDP connected! Chrome version: {data.get('Browser', 'Unknown')}")
                            
                            # Test creating a page
                            async with session.put(f'http://localhost:{debug_port}/json/new?about:blank') as new_resp:
                                if new_resp.status == 200:
                                    page_data = await new_resp.json()
                                    log(f"✅ Page created: {page_data.get('id', 'Unknown')}")
                                else:
                                    log(f"❌ Failed to create page: {new_resp.status}")
                            
                            # Cleanup
                            process.terminate()
                            await process.wait()
                            log("✅ Chrome process terminated cleanly")
                            return True
                        else:
                            log(f"CDP returned status {resp.status}, retrying...")
                            
            except Exception as e:
                log(f"CDP connection attempt {attempt + 1}/10 failed: {e}")
                await asyncio.sleep(1)
        
        log("❌ CDP connection failed after 10 attempts")
        process.terminate()
        await process.wait()
        return False
        
    except Exception as e:
        log(f"❌ Failed to launch Chrome: {e}")
        return False

async def test_browser_use_profile():
    """Test browser startup using browser-use profile system."""
    log("🧪 Testing browser-use profile system...")
    
    try:
        # Import browser-use components
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        from browser_use.browser.profile import BrowserProfile
        from browser_use.browser.watchdogs.local_browser_watchdog import LocalBrowserWatchdog
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Create profile
        profile = BrowserProfile(
            user_data_dir=Path("E:/ai/browser-use/debug_profile"),
            profile_directory="Default",
            executable_path=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            headless=True,
            disable_security=True
        )
        
        log(f"Profile created with {len(profile.get_args())} arguments")
        
        # Create event bus and browser session placeholders for testing
        from bubus import EventBus
        from browser_use.browser.session import BrowserSession
        
        event_bus = EventBus()
        # For testing, we'll create a minimal browser session
        # Note: In production, this would be properly initialized with a Browser instance
        browser_session = BrowserSession(
            browser_profile=profile,
            is_local=True
        )
        
        # Create watchdog with required parameters
        watchdog = LocalBrowserWatchdog(
            event_bus=event_bus, 
            browser_session=browser_session
        )
        
        # Test launch
        log("Attempting browser launch via LocalBrowserWatchdog...")
        
        # This should trigger the problematic code path
        from browser_use.browser.events import BrowserLaunchEvent
        
        event = BrowserLaunchEvent(profile=profile)
        
        # Set a shorter timeout for testing
        import os
        os.environ["BROWSER_START_TIMEOUT_SEC"] = "30"
        
        result = await asyncio.wait_for(
            watchdog.on_BrowserLaunchEvent(event),
            timeout=45
        )
        
        log(f"✅ Browser launch successful: {result}")
        return True
        
    except asyncio.TimeoutError:
        log("❌ Browser launch timed out (45s)")
        return False
    except Exception as e:
        log(f"❌ Browser launch failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all diagnostic tests."""
    log("🚀 Browser Startup Diagnostic")
    log("=" * 50)
    
    # Test 1: Direct Chrome launch
    direct_success = await test_chrome_direct_launch()
    log("")
    
    # Test 2: Browser-use profile system
    profile_success = await test_browser_use_profile()
    log("")
    
    # Summary
    log("=" * 50)
    log("DIAGNOSTIC SUMMARY")
    log("=" * 50)
    
    if direct_success:
        log("✅ Direct Chrome launch: WORKING")
    else:
        log("❌ Direct Chrome launch: FAILED")
    
    if profile_success:
        log("✅ Browser-use profile: WORKING")
    else:
        log("❌ Browser-use profile: FAILED")
    
    if direct_success and not profile_success:
        log("")
        log("🔍 DIAGNOSIS: Chrome works directly but browser-use profile fails")
        log("   → Issue is in browser-use profile/watchdog system")
        log("   → Check profile arguments and watchdog event handling")
    elif not direct_success:
        log("")
        log("🔍 DIAGNOSIS: Chrome itself is not starting properly")
        log("   → Issue is with Chrome installation or system configuration")
        log("   → Check Chrome path, permissions, and system resources")
    else:
        log("")
        log("🎉 DIAGNOSIS: Both systems working - issue may be intermittent")

if __name__ == "__main__":
    asyncio.run(main())