#!/usr/bin/env python3
"""
Simple Browser Test - Validate Basic Functionality
=================================================

Test the most basic browser-use functionality to isolate issues.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from browser_use import BrowserSession, Agent, ChatLlamaCpp

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_basic_browser_session():
    """Test basic browser session creation and navigation."""
    logger.info("Testing basic browser session...")
    
    try:
        # Create a minimal browser session
        session = BrowserSession(
            headless=False,  # Use visible browser for debugging
            user_data_dir=os.getenv("CHROME_USER_DATA_DIR"),
            profile_directory=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
            executable_path=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        )
        
        logger.info("Browser session created successfully")
        
        # Try to start the session
        await session.start()
        logger.info("Browser session started successfully")
        
        # Try basic navigation
        await session.navigate_to_url("https://example.com")
        logger.info("Navigation completed successfully")
        
        # Get page info
        state = await session.get_browser_state_summary()
        logger.info(f"Page title: {state.title}")
        logger.info(f"Page URL: {state.url}")
        
        # Close session
        await session.stop()
        logger.info("Browser session closed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Browser session test failed: {e}")
        return False

async def test_basic_agent():
    """Test basic agent functionality."""
    logger.info("Testing basic agent functionality...")
    
    try:
        # Create local LLM
        llm = ChatLlamaCpp(
            model="qwen2.5-14b-instruct-q4_k_m.gguf",
            base_url="http://localhost:8080",
            timeout=30,
            temperature=0.1
        )
        
        # Create browser session
        session = BrowserSession(
            headless=False,
            user_data_dir=os.getenv("CHROME_USER_DATA_DIR"),
            profile_directory=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
            executable_path=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        )
        
        # Create agent
        agent = Agent(
            task="Navigate to example.com and tell me the main heading",
            llm=llm,
            browser=session
        )
        
        logger.info("Agent created successfully")
        
        # Run agent with timeout
        result = await asyncio.wait_for(agent.run(), timeout=60)
        
        logger.info(f"Agent completed successfully")
        logger.info(f"Result: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        return False

async def main():
    """Run all tests."""
    load_dotenv()
    
    logger.info("Starting browser-use functionality tests...")
    
    # Test 1: Basic browser session
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Basic Browser Session")
    logger.info("="*50)
    
    browser_test_passed = await test_basic_browser_session()
    
    # Test 2: Basic agent (only if browser test passed)
    if browser_test_passed:
        logger.info("\n" + "="*50)
        logger.info("TEST 2: Basic Agent")
        logger.info("="*50)
        
        agent_test_passed = await test_basic_agent()
    else:
        agent_test_passed = False
        logger.warning("Skipping agent test due to browser session failure")
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    logger.info(f"Browser Session Test: {'PASSED' if browser_test_passed else 'FAILED'}")
    logger.info(f"Agent Test: {'PASSED' if agent_test_passed else 'FAILED'}")
    
    if browser_test_passed and agent_test_passed:
        logger.info("✅ All tests passed - browser-use is working correctly")
        return True
    else:
        logger.error("❌ Some tests failed - browser-use has issues")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)