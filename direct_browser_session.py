#!/usr/bin/env python3
"""
Direct Browser Session - CDP Connection Fix
==========================================

Alternative browser integration that bypasses the LocalBrowserWatchdog
timeout issues by using direct CDP connections and simplified session management.

This addresses the critical CDP connection failure that blocks all functionality.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

logger = logging.getLogger(__name__)

@dataclass
class BrowserState:
    """Simple browser state representation."""
    url: str = "about:blank"
    title: str = ""
    page_text: str = ""
    tabs: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tabs is None:
            self.tabs = []

class DirectBrowserSession:
    """
    Direct browser session that bypasses browser-use's complex event system.
    
    Uses direct CDP connections to avoid LocalBrowserWatchdog timeout issues.
    Provides simplified, reliable browser automation for the hybrid LLM system.
    """
    
    def __init__(
        self,
        executable_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        profile_directory: str = "Default",
        headless: bool = False,
        debug_port: int = 9222,
        timeout: float = 30.0
    ):
        self.executable_path = executable_path or self._find_chrome_executable()
        self.user_data_dir = user_data_dir
        self.profile_directory = profile_directory
        self.headless = headless
        self.debug_port = debug_port
        self.timeout = timeout
        
        # Runtime state
        self.process: Optional[subprocess.Popen] = None
        self.cdp_url: Optional[str] = None
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.current_tab_id: Optional[str] = None
        self.temp_profile_dir: Optional[str] = None
        
        # CDP message tracking
        self._message_id = 0
        self._pending_responses: Dict[int, asyncio.Future] = {}
        
        logger.info(f"[DIRECT] Initialized DirectBrowserSession with Chrome: {self.executable_path}")
    
    def _find_chrome_executable(self) -> str:
        """Find Chrome executable on Windows."""
        # Try environment variable first
        chrome_path = os.getenv("CHROME_EXECUTABLE")
        if chrome_path and os.path.exists(chrome_path):
            return chrome_path
        
        # Try common Windows paths
        common_paths = [
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError("Chrome executable not found. Please set CHROME_EXECUTABLE environment variable.")
    
    async def start(self) -> bool:
        """Start browser session with direct CDP connection."""
        logger.info("[DIRECT] Starting direct browser session...")
        
        try:
            # Step 1: Prepare profile
            await self._prepare_profile()
            
            # Step 2: Launch Chrome with CDP
            await self._launch_chrome()
            
            # Step 3: Connect to CDP
            await self._connect_cdp()
            
            # Step 4: Initialize browser state
            await self._initialize_browser()
            
            logger.info("[DIRECT] Browser session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"[DIRECT] Failed to start browser session: {e}")
            await self.close()
            return False
    
    async def _prepare_profile(self):
        """Prepare Chrome profile for use."""
        # Always use a temporary profile directory to avoid conflicts
        self.temp_profile_dir = tempfile.mkdtemp(prefix="chrome_direct_")
        
        if self.user_data_dir and os.path.exists(self.user_data_dir):
            # Copy existing profile to temporary location
            source_profile = os.path.join(self.user_data_dir, self.profile_directory)
            dest_profile = os.path.join(self.temp_profile_dir, self.profile_directory)
            
            if os.path.exists(source_profile):
                logger.info(f"[DIRECT] Copying profile from {source_profile} to {dest_profile}")
                try:
                    shutil.copytree(source_profile, dest_profile, ignore_dangling_symlinks=True)
                    logger.info(f"[DIRECT] Profile copied successfully")
                except Exception as e:
                    logger.warning(f"[DIRECT] Profile copy failed (using empty profile): {e}")
            else:
                logger.info(f"[DIRECT] Source profile not found, using empty profile: {source_profile}")
        else:
            logger.info(f"[DIRECT] No user data dir specified, using empty profile")
        
        # Always use the temporary directory
        self.user_data_dir = self.temp_profile_dir
        logger.info(f"[DIRECT] Using profile directory: {self.user_data_dir}")
    
    async def _launch_chrome(self):
        """Launch Chrome with CDP enabled."""
        logger.info(f"[DIRECT] Launching Chrome on debug port {self.debug_port}")
        
        # Build Chrome command line arguments
        args = [
            self.executable_path,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={self.user_data_dir}",
            f"--profile-directory={self.profile_directory}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--disable-features=VizDisplayCompositor",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",  # For development/testing
        ]
        
        if self.headless:
            args.extend(["--headless", "--disable-gpu"])
        
        # Disable extensions for stability
        if os.getenv("ENABLE_DEFAULT_EXTENSIONS", "0") == "0":
            args.append("--disable-extensions")
        
        # Launch Chrome
        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            logger.info(f"[DIRECT] Chrome launched with PID: {self.process.pid}")
            
            # Wait for Chrome to start
            await asyncio.sleep(2)
            
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise Exception(f"Chrome process exited immediately. Stderr: {stderr.decode()}")
            
        except Exception as e:
            raise Exception(f"Failed to launch Chrome: {e}")
    
    async def _connect_cdp(self):
        """Connect to Chrome DevTools Protocol."""
        logger.info("[DIRECT] Connecting to CDP...")
        
        # Wait for CDP to be available
        cdp_base_url = f"http://localhost:{self.debug_port}"
        
        for attempt in range(10):  # 10 attempts, 1 second each
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{cdp_base_url}/json/version")
                    if response.status_code == 200:
                        version_info = response.json()
                        logger.info(f"[DIRECT] CDP available - Chrome {version_info.get('Browser', 'Unknown')}")
                        break
            except Exception as e:
                logger.debug(f"[DIRECT] CDP not ready (attempt {attempt + 1}): {e}")
                await asyncio.sleep(1)
        else:
            raise Exception("CDP endpoint not available after 10 seconds")
        
        # Get list of tabs
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{cdp_base_url}/json")
                tabs = response.json()
                
                if not tabs:
                    raise Exception("No tabs available")
                
                # Use first available tab
                target_tab = tabs[0]
                self.current_tab_id = target_tab['id']
                websocket_url = target_tab['webSocketDebuggerUrl']
                
                logger.info(f"[DIRECT] Connecting to tab {self.current_tab_id}")
                
                # Connect to WebSocket (fix timeout parameter for older websockets versions)
                self.websocket = await websockets.connect(
                    websocket_url,
                    max_size=10 * 1024 * 1024,  # 10MB max message size
                    ping_interval=None,  # Disable ping/pong
                    ping_timeout=None
                )
                
                logger.info("[DIRECT] CDP WebSocket connected successfully")
                
                # Start message handler
                asyncio.create_task(self._handle_cdp_messages())
                
        except Exception as e:
            raise Exception(f"Failed to connect to CDP WebSocket: {e}")
    
    async def _handle_cdp_messages(self):
        """Handle incoming CDP messages."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle responses to our requests
                    if 'id' in data and data['id'] in self._pending_responses:
                        future = self._pending_responses.pop(data['id'])
                        if not future.cancelled():
                            future.set_result(data)
                    
                    # Handle events (could be used for monitoring)
                    elif 'method' in data:
                        logger.debug(f"[DIRECT] CDP Event: {data['method']}")
                
                except json.JSONDecodeError:
                    logger.warning(f"[DIRECT] Invalid JSON from CDP: {message}")
                except Exception as e:
                    logger.warning(f"[DIRECT] Error handling CDP message: {e}")
                    
        except ConnectionClosed:
            logger.info("[DIRECT] CDP WebSocket connection closed")
        except Exception as e:
            logger.error(f"[DIRECT] CDP message handler error: {e}")
    
    async def _send_cdp_command(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send CDP command and wait for response."""
        if not self.websocket:
            raise Exception("CDP WebSocket not connected")
        
        self._message_id += 1
        message = {
            "id": self._message_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.Future()
        self._pending_responses[self._message_id] = future
        
        try:
            # Send message
            await self.websocket.send(json.dumps(message))
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=self.timeout)
            
            if 'error' in response:
                raise Exception(f"CDP Error: {response['error']}")
            
            return response.get('result', {})
            
        except asyncio.TimeoutError:
            self._pending_responses.pop(self._message_id, None)
            raise Exception(f"CDP command timeout: {method}")
        except Exception as e:
            self._pending_responses.pop(self._message_id, None)
            raise Exception(f"CDP command failed: {method} - {e}")
    
    async def _initialize_browser(self):
        """Initialize browser state and enable required domains."""
        logger.info("[DIRECT] Initializing browser state...")
        
        try:
            # Enable required CDP domains
            await self._send_cdp_command("Runtime.enable")
            await self._send_cdp_command("Page.enable")
            await self._send_cdp_command("DOM.enable")
            
            logger.info("[DIRECT] Browser initialized successfully")
            
        except Exception as e:
            raise Exception(f"Failed to initialize browser: {e}")
    
    async def navigate_to_url(self, url: str) -> bool:
        """Navigate to a URL."""
        logger.info(f"[DIRECT] Navigating to: {url}")
        
        try:
            result = await self._send_cdp_command("Page.navigate", {"url": url})
            
            # Wait for navigation to complete
            await asyncio.sleep(2)
            
            logger.info(f"[DIRECT] Navigation completed")
            return True
            
        except Exception as e:
            logger.error(f"[DIRECT] Navigation failed: {e}")
            return False
    
    async def get_browser_state(self) -> BrowserState:
        """Get current browser state."""
        try:
            # Get page info
            url_result = await self._send_cdp_command("Runtime.evaluate", {
                "expression": "window.location.href"
            })
            url = url_result.get('result', {}).get('value', 'about:blank')
            
            title_result = await self._send_cdp_command("Runtime.evaluate", {
                "expression": "document.title"
            })
            title = title_result.get('result', {}).get('value', '')
            
            # Get page text (simplified)
            text_result = await self._send_cdp_command("Runtime.evaluate", {
                "expression": "document.body ? document.body.innerText.substring(0, 5000) : ''"
            })
            page_text = text_result.get('result', {}).get('value', '')
            
            return BrowserState(
                url=url,
                title=title,
                page_text=page_text,
                tabs=[{"id": self.current_tab_id, "url": url, "title": title}]
            )
            
        except Exception as e:
            logger.error(f"[DIRECT] Failed to get browser state: {e}")
            return BrowserState()
    
    async def execute_javascript(self, script: str) -> Any:
        """Execute JavaScript in the current page."""
        try:
            result = await self._send_cdp_command("Runtime.evaluate", {
                "expression": script,
                "returnByValue": True
            })
            
            return result.get('result', {}).get('value')
            
        except Exception as e:
            logger.error(f"[DIRECT] JavaScript execution failed: {e}")
            return None
    
    async def click_element(self, selector: str) -> bool:
        """Click an element by CSS selector."""
        script = f"""
        (function() {{
            const element = document.querySelector('{selector}');
            if (element) {{
                element.click();
                return true;
            }}
            return false;
        }})()
        """
        
        result = await self.execute_javascript(script)
        return bool(result)
    
    async def type_text(self, selector: str, text: str) -> bool:
        """Type text into an element."""
        script = f"""
        (function() {{
            const element = document.querySelector('{selector}');
            if (element) {{
                element.focus();
                element.value = '{text}';
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }})()
        """
        
        result = await self.execute_javascript(script)
        return bool(result)
    
    async def close(self):
        """Close browser session and cleanup."""
        logger.info("[DIRECT] Closing browser session...")
        
        try:
            # Close WebSocket
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            
            # Terminate Chrome process
            if self.process:
                self.process.terminate()
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process()),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("[DIRECT] Chrome process didn't terminate gracefully, killing...")
                    self.process.kill()
                
                self.process = None
            
            # Cleanup temporary profile
            if self.temp_profile_dir and os.path.exists(self.temp_profile_dir):
                try:
                    shutil.rmtree(self.temp_profile_dir)
                    logger.info(f"[DIRECT] Cleaned up temporary profile: {self.temp_profile_dir}")
                except Exception as e:
                    logger.warning(f"[DIRECT] Failed to cleanup temporary profile: {e}")
            
            logger.info("[DIRECT] Browser session closed")
            
        except Exception as e:
            logger.error(f"[DIRECT] Error during cleanup: {e}")
    
    async def _wait_for_process(self):
        """Wait for Chrome process to terminate."""
        while self.process and self.process.poll() is None:
            await asyncio.sleep(0.1)


# Test function for direct browser session
async def test_direct_browser_session():
    """Test the direct browser session implementation."""
    logger.info("Testing DirectBrowserSession...")
    
    session = DirectBrowserSession(
        executable_path=os.getenv("CHROME_EXECUTABLE"),
        user_data_dir=os.getenv("CHROME_USER_DATA_DIR"),
        profile_directory=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
        headless=False  # Use visible browser for testing
    )
    
    try:
        # Start session
        success = await session.start()
        if not success:
            logger.error("Failed to start browser session")
            return False
        
        # Navigate to test page
        await session.navigate_to_url("https://example.com")
        
        # Get browser state
        state = await session.get_browser_state()
        logger.info(f"Page title: {state.title}")
        logger.info(f"Page URL: {state.url}")
        logger.info(f"Page text preview: {state.page_text[:200]}...")
        
        # Test JavaScript execution
        heading = await session.execute_javascript("document.querySelector('h1') ? document.querySelector('h1').textContent : 'No heading found'")
        logger.info(f"Main heading: {heading}")
        
        logger.info("✅ DirectBrowserSession test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ DirectBrowserSession test failed: {e}")
        return False
        
    finally:
        await session.close()


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
    
    # Load environment
    load_dotenv()
    
    # Run test
    success = asyncio.run(test_direct_browser_session())
    sys.exit(0 if success else 1)