#!/usr/bin/env python3
"""
Emergency Browser Startup Fix
============================

Implements a simplified browser launcher that bypasses the complex watchdog system
to get basic functionality working immediately.
"""

import asyncio
import subprocess
import time
import psutil
import requests
from pathlib import Path
from typing import Optional

def log(message: str):
    """Log with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] [EMERGENCY_FIX] {message}")

def kill_chrome_processes():
    """Kill all existing Chrome processes."""
    killed_count = 0
    for proc in psutil.process_iter():
        try:
            if 'chrome' in proc.name().lower():
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if killed_count > 0:
        log(f"Killed {killed_count} Chrome processes")
        time.sleep(2)  # Wait for cleanup

async def simple_chrome_launch(port: int = 9222) -> Optional[subprocess.Popen]:
    """Launch Chrome with minimal configuration for maximum reliability."""
    
    chrome_exe = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
    if not Path(chrome_exe).exists():
        chrome_exe = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not Path(chrome_exe).exists():
            log("Chrome executable not found")
            return None
    
    # Create minimal user data directory
    user_data_dir = Path("E:\\ai\\browser-use\\runtime\\emergency_profile")
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Minimal Chrome arguments for maximum compatibility
    cmd = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
        "--disable-dev-shm-usage",
        "--no-sandbox",  # For compatibility
        "--disable-gpu-sandbox",
        "about:blank"
    ]
    
    log(f"Launching Chrome on port {port}...")
    
    try:
        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        
        log(f"Chrome launched with PID: {proc.pid}")
        
        # Wait for CDP to be available with shorter timeout
        for i in range(15):  # 15 seconds max
            try:
                response = requests.get(f"http://localhost:{port}/json/version", timeout=1)
                if response.status_code == 200:
                    log(f"CDP available after {i+1} seconds")
                    version_info = response.json()
                    log(f"Chrome version: {version_info.get('Browser', 'Unknown')}")
                    return proc
            except requests.RequestException:
                await asyncio.sleep(1)
        
        log("CDP connection failed - terminating Chrome")
        proc.terminate()
        return None
        
    except Exception as e:
        log(f"Failed to launch Chrome: {e}")
        return None

async def test_emergency_fix():
    """Test the emergency browser fix."""
    log("Starting emergency browser fix test...")
    
    # Clean slate
    kill_chrome_processes()
    
    # Try to launch Chrome
    proc = await simple_chrome_launch()
    
    if proc:
        log("✅ Emergency fix successful - Chrome is running with CDP")
        
        # Test basic CDP functionality
        try:
            # Get tabs
            response = requests.get("http://localhost:9222/json", timeout=5)
            if response.status_code == 200:
                tabs = response.json()
                log(f"Found {len(tabs)} tabs")
                
                if tabs:
                    tab = tabs[0]
                    log(f"Active tab: {tab.get('title', 'Unknown')} - {tab.get('url', 'Unknown')}")
                
                log("✅ Basic CDP functionality confirmed")
                return True
            else:
                log(f"❌ Failed to get tabs: {response.status_code}")
                
        except Exception as e:
            log(f"❌ CDP test failed: {e}")
        
        finally:
            # Clean up
            proc.terminate()
            await asyncio.sleep(1)
            if proc.poll() is None:
                proc.kill()
    
    else:
        log("❌ Emergency fix failed - could not launch Chrome")
        return False

async def main():
    """Main emergency fix function."""
    log("Emergency Browser Startup Fix")
    log("=" * 50)
    log("This script bypasses the complex browser-use watchdog system")
    log("to establish basic Chrome CDP connectivity for debugging.")
    log("")
    
    success = await test_emergency_fix()
    
    log("")
    log("=" * 50)
    if success:
        log("🎉 EMERGENCY FIX SUCCESSFUL")
        log("")
        log("Next steps:")
        log("1. Integrate this simplified launcher into browser-use")
        log("2. Replace complex watchdog system with direct CDP connection")
        log("3. Add proper error handling and retries")
        log("4. Test with actual browser-use agent")
    else:
        log("❌ EMERGENCY FIX FAILED")
        log("")
        log("This indicates deeper system issues:")
        log("1. Chrome installation problems")
        log("2. Windows security/firewall blocking CDP")
        log("3. Port conflicts")
        log("4. System resource constraints")

if __name__ == "__main__":
    asyncio.run(main())