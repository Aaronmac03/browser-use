#!/usr/bin/env python3
"""
Minimal Test Script - Validates Core Components
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    print("=== Minimal Component Test ===")
    load_dotenv()
    
    # Test 1: LLM Connection
    print("1. Testing LLM connection...")
    try:
        from runner import make_local_llm
        llm = make_local_llm()
        response = await llm.ainvoke("What is 2+2?")
        print(f"   LLM Response: {response.content[:50]}...")
        print("   [PASS] LLM working")
    except Exception as e:
        print(f"   [FAIL] LLM error: {e}")
        return False
    
    # Test 2: Cloud Planning
    print("2. Testing cloud planning...")
    try:
        from runner import plan_with_o3_then_gemini
        subtasks = await plan_with_o3_then_gemini("Visit example.com")
        print(f"   Generated {len(subtasks)} subtasks")
        print("   [PASS] Cloud planning working")
    except Exception as e:
        print(f"   [FAIL] Cloud planning error: {e}")
        return False
        
    # Test 3: Browser Startup
    print("3. Testing browser startup...")
    try:
        from runner import make_browser
        browser = make_browser()
        await browser.start()
        await browser.stop()
        print("   [PASS] Browser startup working")
    except Exception as e:
        print(f"   [FAIL] Browser startup error: {e}")
        return False
    
    print("=== ALL TESTS PASSED ===")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)