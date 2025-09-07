#!/usr/bin/env python3
"""
Simple CDP Connection Test
=========================

Test basic Chrome DevTools Protocol connection without complex features.
This isolates the CDP connection issue to find the minimal working configuration.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_basic_cdp_connection():
    """Test basic CDP connection with minimal Chrome configuration."""
    logger.info("Testing basic CDP connection...")
    
    # Create temporary profile
    temp_dir = tempfile.mkdtemp(prefix="chrome_cdp_test_")
    logger.info(f"Using temporary profile: {temp_dir}")
    
    # Chrome executable
    chrome_exe = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_exe):
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    if not os.path.exists(chrome_exe):
        logger.error("Chrome executable not found")
        return False
    
    # Minimal Chrome arguments for CDP
    debug_port = 9223  # Use different port to avoid conflicts
    args = [
        chrome_exe,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-sync",
        "--disable-default-apps",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--headless",  # Use headless for testing
        "--disable-gpu"
    ]
    
    process = None
    try:
        # Launch Chrome
        logger.info(f"Launching Chrome with CDP on port {debug_port}")
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        logger.info(f"Chrome launched with PID: {process.pid}")
        
        # Wait for Chrome to start
        await asyncio.sleep(3)
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(f"Chrome exited immediately. Stderr: {stderr.decode()}")
            return False
        
        # Test CDP endpoint availability
        cdp_base_url = f"http://localhost:{debug_port}"
        
        for attempt in range(15):  # 15 attempts, 1 second each
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{cdp_base_url}/json/version")
                    if response.status_code == 200:
                        version_info = response.json()
                        logger.info(f"✅ CDP available - Chrome {version_info.get('Browser', 'Unknown')}")
                        
                        # Test getting tabs
                        tabs_response = await client.get(f"{cdp_base_url}/json")
                        tabs = tabs_response.json()
                        logger.info(f"✅ Found {len(tabs)} tabs")
                        
                        if tabs:
                            tab = tabs[0]
                            logger.info(f"✅ First tab: {tab.get('title', 'No title')} - {tab.get('url', 'No URL')}")
                        
                        logger.info("✅ CDP connection test PASSED")
                        return True
                        
            except Exception as e:
                logger.debug(f"CDP not ready (attempt {attempt + 1}): {e}")
                await asyncio.sleep(1)
        
        logger.error("❌ CDP endpoint not available after 15 seconds")
        return False
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup
        if process:
            try:
                process.terminate()
                await asyncio.sleep(2)
                if process.poll() is None:
                    process.kill()
                logger.info("Chrome process terminated")
            except Exception as e:
                logger.warning(f"Error terminating Chrome: {e}")
        
        # Cleanup temp directory
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info("Temporary profile cleaned up")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp profile: {e}")

async def test_websocket_connection():
    """Test WebSocket connection to CDP."""
    logger.info("Testing WebSocket CDP connection...")
    
    # Create temporary profile
    temp_dir = tempfile.mkdtemp(prefix="chrome_ws_test_")
    logger.info(f"Using temporary profile: {temp_dir}")
    
    # Chrome executable
    chrome_exe = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_exe):
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    # Minimal Chrome arguments
    debug_port = 9224  # Different port
    args = [
        chrome_exe,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--headless",
        "--disable-gpu"
    ]
    
    process = None
    try:
        # Launch Chrome
        logger.info(f"Launching Chrome for WebSocket test on port {debug_port}")
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for startup
        await asyncio.sleep(3)
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(f"Chrome exited. Stderr: {stderr.decode()}")
            return False
        
        # Get WebSocket URL
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://localhost:{debug_port}/json")
            tabs = response.json()
            
            if not tabs:
                logger.error("No tabs available")
                return False
            
            ws_url = tabs[0]['webSocketDebuggerUrl']
            logger.info(f"WebSocket URL: {ws_url}")
            
            # Test WebSocket connection
            import websockets
            
            try:
                async with websockets.connect(ws_url, timeout=10) as websocket:
                    logger.info("✅ WebSocket connected successfully")
                    
                    # Send a simple CDP command
                    command = {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": "1 + 1"}
                    }
                    
                    await websocket.send(json.dumps(command))
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    
                    result = json.loads(response)
                    logger.info(f"✅ CDP command result: {result}")
                    
                    if result.get('result', {}).get('result', {}).get('value') == 2:
                        logger.info("✅ WebSocket CDP test PASSED")
                        return True
                    else:
                        logger.error("❌ Unexpected CDP result")
                        return False
                        
            except Exception as e:
                logger.error(f"❌ WebSocket connection failed: {e}")
                return False
        
    except Exception as e:
        logger.error(f"❌ WebSocket test failed: {e}")
        return False
        
    finally:
        # Cleanup
        if process:
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.poll() is None:
                    process.kill()
            except Exception as e:
                logger.warning(f"Error terminating Chrome: {e}")
        
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup: {e}")

async def main():
    """Run CDP connection tests."""
    logger.info("Starting CDP connection tests...")
    
    # Test 1: Basic HTTP CDP endpoint
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Basic CDP HTTP Endpoint")
    logger.info("="*50)
    
    http_test_passed = await test_basic_cdp_connection()
    
    # Test 2: WebSocket CDP connection (only if HTTP test passed)
    if http_test_passed:
        logger.info("\n" + "="*50)
        logger.info("TEST 2: WebSocket CDP Connection")
        logger.info("="*50)
        
        ws_test_passed = await test_websocket_connection()
    else:
        ws_test_passed = False
        logger.warning("Skipping WebSocket test due to HTTP test failure")
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("CDP CONNECTION TEST SUMMARY")
    logger.info("="*50)
    logger.info(f"HTTP CDP Test: {'PASSED' if http_test_passed else 'FAILED'}")
    logger.info(f"WebSocket CDP Test: {'PASSED' if ws_test_passed else 'FAILED'}")
    
    if http_test_passed and ws_test_passed:
        logger.info("✅ All CDP tests passed - Direct browser approach is viable")
        return True
    else:
        logger.error("❌ CDP tests failed - Need alternative approach")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)