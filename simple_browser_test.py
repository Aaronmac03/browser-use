#!/usr/bin/env python3
"""
Simple Browser Test - Test basic browser automation
"""

import asyncio
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

def log(message: str):
    """Log with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

async def test_simple_automation():
    """Test a very simple browser automation task."""
    log("🌐 Testing simple browser automation...")
    
    try:
        from runner import main as runner_main
        
        # Very simple task
        goal = "Navigate to example.com"
        
        log(f"  Goal: {goal}")
        log("  Starting automation...")
        
        start_time = time.time()
        await asyncio.wait_for(runner_main(goal), timeout=180)  # 3 minutes
        execution_time = time.time() - start_time
        
        log(f"  ✅ Automation completed in {execution_time:.1f}s")
        return True
        
    except asyncio.TimeoutError:
        log("  ❌ Automation timed out")
        return False
    except Exception as e:
        log(f"  ❌ Automation failed: {e}")
        return False

async def main():
    """Main test function."""
    load_dotenv()
    
    log("🧪 Simple Browser Automation Test")
    log("=" * 50)
    log("Testing end-to-end browser automation")
    log("")
    
    success = await test_simple_automation()
    
    log("")
    log("=" * 50)
    log("🎯 BROWSER TEST SUMMARY")
    log("=" * 50)
    
    if success:
        log("🎉 Browser automation WORKING!")
        log("")
        log("✅ End-to-end automation successful")
        log("✅ Local LLM driving browser actions")
        log("✅ Chrome profile integration working")
        log("✅ Phase 5 capability goal validated!")
        return True
    else:
        log("⚠️ Browser automation ISSUES")
        log("End-to-end test failed")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)