#!/usr/bin/env python3
"""Simple browser startup test."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_browser_startup():
    """Test browser startup with different strategies."""
    load_dotenv()
    
    from runner import make_browser
    
    print("Testing browser startup...")
    
    try:
        browser = make_browser()
        print("Browser created successfully")
        
        print("Starting browser...")
        await asyncio.wait_for(browser.start(), timeout=60)
        print("Browser started successfully!")
        
        print("Stopping browser...")
        await browser.stop()
        print("Browser stopped successfully!")
        
        return True
        
    except Exception as e:
        print(f"Browser startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_browser_startup())
    sys.exit(0 if success else 1)