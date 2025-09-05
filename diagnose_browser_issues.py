#!/usr/bin/env python3
"""
Browser Startup Diagnostic Script
=================================

Diagnoses the browser startup issues seen in the E2E tests.
The main issue appears to be CDP connection timeouts.
"""

import asyncio
import sys
import time
import subprocess
import psutil
from pathlib import Path
from dotenv import load_dotenv

def log(message: str):
    """Log with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def check_chrome_processes():
    """Check for existing Chrome processes."""
    chrome_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'chrome' in proc.info['name'].lower():
                chrome_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': ' '.join(proc.info['cmdline'][:3]) if proc.info['cmdline'] else ''
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return chrome_processes

def check_chrome_executable():
    """Check Chrome executable path."""
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
    ]
    
    for path in chrome_paths:
        if Path(path).exists():
            log(f"Found Chrome at: {path}")
            return path
    
    log("Chrome executable not found in standard locations")
    return None

def check_user_data_dir():
    """Check Chrome user data directory."""
    user_data_paths = [
        "C:\\Users\\drmcn\\AppData\\Local\\Google\\Chrome\\User Data",
        "E:\\ai\\browser-use\\runtime\\user_data"
    ]
    
    for path in user_data_paths:
        if Path(path).exists():
            log(f"Found user data dir: {path}")
            # Check if Default profile exists
            default_profile = Path(path) / "Default"
            if default_profile.exists():
                log(f"  Default profile exists: {default_profile}")
            else:
                log(f"  Default profile missing: {default_profile}")
        else:
            log(f"User data dir missing: {path}")

async def test_basic_chrome_launch():
    """Test basic Chrome launch with CDP."""
    log("Testing basic Chrome launch with CDP...")
    
    chrome_exe = check_chrome_executable()
    if not chrome_exe:
        return False
    
    # Kill existing Chrome processes
    log("Killing existing Chrome processes...")
    for proc in psutil.process_iter():
        try:
            if 'chrome' in proc.name().lower():
                proc.kill()
                log(f"Killed Chrome process: {proc.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    await asyncio.sleep(2)
    
    # Launch Chrome with CDP
    cmd = [
        chrome_exe,
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
        "--user-data-dir=E:\\ai\\browser-use\\runtime\\user_data_test",
        "--profile-directory=Default",
        "about:blank"
    ]
    
    log(f"Launching Chrome with command: {' '.join(cmd[:5])}...")
    
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"Chrome launched with PID: {proc.pid}")
        
        # Wait for CDP to be available
        import requests
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get("http://localhost:9222/json/version", timeout=2)
                if response.status_code == 200:
                    log(f"CDP available after {i+1} seconds")
                    log(f"Chrome version: {response.json().get('Browser', 'Unknown')}")
                    
                    # Test getting tabs
                    tabs_response = requests.get("http://localhost:9222/json", timeout=2)
                    if tabs_response.status_code == 200:
                        tabs = tabs_response.json()
                        log(f"Found {len(tabs)} tabs")
                        return True
                    else:
                        log(f"Failed to get tabs: {tabs_response.status_code}")
                        return False
                        
            except requests.RequestException:
                await asyncio.sleep(1)
        
        log("CDP never became available")
        return False
        
    except Exception as e:
        log(f"Failed to launch Chrome: {e}")
        return False
    finally:
        # Clean up
        try:
            proc.terminate()
            await asyncio.sleep(1)
            if proc.poll() is None:
                proc.kill()
        except:
            pass

async def test_browser_use_components():
    """Test browser-use components individually."""
    log("Testing browser-use components...")
    
    try:
        # Test imports
        log("Testing imports...")
        from browser_use.browser.browser import Browser
        from browser_use.browser.profile import BrowserProfile
        log("Imports successful")
        
        # Test profile creation
        log("Testing profile creation...")
        profile = BrowserProfile(
            user_data_dir="E:\\ai\\browser-use\\runtime\\user_data",
            profile_directory="Default",
            chrome_executable="C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        )
        log(f"Profile created with {len(profile.get_args())} arguments")
        
        # Test browser creation (but don't start)
        log("Testing browser creation...")
        browser = Browser(profile=profile)
        log("Browser object created successfully")
        
        return True
        
    except Exception as e:
        log(f"Component test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main diagnostic function."""
    load_dotenv()
    
    log("Browser Startup Diagnostic")
    log("=" * 50)
    
    # System checks
    log("1. System Environment Checks")
    log("-" * 30)
    
    log(f"Python version: {sys.version}")
    log(f"Platform: {sys.platform}")
    
    # Chrome checks
    log("\n2. Chrome Environment Checks")
    log("-" * 30)
    
    chrome_exe = check_chrome_executable()
    check_user_data_dir()
    
    existing_procs = check_chrome_processes()
    if existing_procs:
        log(f"Found {len(existing_procs)} existing Chrome processes:")
        for proc in existing_procs[:3]:  # Show first 3
            log(f"  PID {proc['pid']}: {proc['name']} - {proc['cmdline']}")
    else:
        log("No existing Chrome processes found")
    
    # Component tests
    log("\n3. Browser-Use Component Tests")
    log("-" * 30)
    
    components_ok = await test_browser_use_components()
    
    # Basic Chrome launch test
    log("\n4. Basic Chrome Launch Test")
    log("-" * 30)
    
    chrome_ok = await test_basic_chrome_launch()
    
    # Summary
    log("\n5. Diagnostic Summary")
    log("-" * 30)
    
    if chrome_exe and components_ok and chrome_ok:
        log("✅ All basic tests passed")
        log("The issue may be in browser-use's CDP handling or event system")
        log("Recommendations:")
        log("  - Check browser-use version compatibility")
        log("  - Review CDP timeout settings")
        log("  - Consider using simpler browser profile")
    else:
        log("❌ Basic tests failed")
        log("Issues found:")
        if not chrome_exe:
            log("  - Chrome executable not found")
        if not components_ok:
            log("  - Browser-use component issues")
        if not chrome_ok:
            log("  - Chrome CDP launch issues")

if __name__ == "__main__":
    asyncio.run(main())