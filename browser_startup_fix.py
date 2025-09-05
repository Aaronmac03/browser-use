#!/usr/bin/env python3
"""
Browser startup fix for browser-use system.
Implements alternative startup methods when standard approach fails.
"""

import asyncio
import os
import subprocess
import time
import httpx
from pathlib import Path
from typing import Optional, Tuple

def log(*args):
    print("[startup-fix]", *args, flush=True)

class BrowserStartupFix:
    """Alternative browser startup methods for reliability."""
    
    def __init__(self):
        self.chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    
    def find_chrome_executable(self) -> Optional[str]:
        """Find a working Chrome executable."""
        for path in self.chrome_paths:
            if Path(path).exists():
                log(f"Found Chrome at: {path}")
                return path
        return None
    
    async def start_chrome_with_remote_debugging(self, port: int = 9222) -> Optional[str]:
        """Start Chrome with remote debugging enabled."""
        chrome_exe = self.find_chrome_executable()
        if not chrome_exe:
            log("No Chrome executable found")
            return None
        
        # Create minimal user data directory
        user_data_dir = Path("e:/ai/browser-use/runtime/chrome_minimal")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Minimal Chrome args for stability
        args = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-sync",
            "--disable-translate",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-ipc-flooding-protection",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-dev-shm-usage",
            "--disable-gpu-sandbox",
            "--no-sandbox",  # For reliability in some environments
            "about:blank"
        ]
        
        log(f"Starting Chrome on port {port}...")
        try:
            # Start Chrome process
            process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Wait for CDP to be available
            cdp_url = f"http://localhost:{port}"
            for attempt in range(30):  # 30 seconds max
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{cdp_url}/json/version", timeout=2)
                        if response.status_code == 200:
                            log(f"Chrome CDP available at {cdp_url}")
                            return cdp_url
                except Exception:
                    pass
                
                await asyncio.sleep(1)
                log(f"Waiting for Chrome CDP... attempt {attempt + 1}/30")
            
            log("Chrome CDP not available after 30 seconds")
            process.terminate()
            return None
            
        except Exception as e:
            log(f"Failed to start Chrome: {e}")
            return None
    
    async def test_cdp_connection(self, cdp_url: str) -> bool:
        """Test if CDP connection is working."""
        try:
            async with httpx.AsyncClient() as client:
                # Test version endpoint
                response = await client.get(f"{cdp_url}/json/version", timeout=5)
                if response.status_code != 200:
                    return False
                
                # Test list endpoint
                response = await client.get(f"{cdp_url}/json/list", timeout=5)
                if response.status_code != 200:
                    return False
                
                log("CDP connection test passed")
                return True
                
        except Exception as e:
            log(f"CDP connection test failed: {e}")
            return False

async def main():
    """Test the browser startup fix."""
    log("Testing browser startup fix...")
    
    fix = BrowserStartupFix()
    
    # Try to start Chrome with remote debugging
    cdp_url = await fix.start_chrome_with_remote_debugging(9223)
    
    if cdp_url:
        log(f"✅ Chrome started successfully: {cdp_url}")
        
        # Test CDP connection
        if await fix.test_cdp_connection(cdp_url):
            log("✅ CDP connection working")
        else:
            log("❌ CDP connection failed")
    else:
        log("❌ Failed to start Chrome")

if __name__ == "__main__":
    asyncio.run(main())