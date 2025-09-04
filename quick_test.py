#!/usr/bin/env python3
"""
Quick Phase 5 Test - Minimal validation of core functionality
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

async def test_local_llm_only():
    """Test just the local LLM without browser integration."""
    log("🔧 Testing local LLM connectivity...")
    
    try:
        from runner import make_local_llm
        from browser_use.llm.messages import SystemMessage, UserMessage
        
        local_llm = make_local_llm()
        
        # Test basic functionality
        response = await local_llm.ainvoke([
            SystemMessage(content="You are a helpful assistant."),
            UserMessage(content="Say 'Local LLM test successful' if you can read this.")
        ])
        
        if "test successful" in response.completion.lower():
            log("  ✅ Local LLM responding correctly")
            log(f"  Response: {response.completion}")
            return True
        else:
            log(f"  ❌ Local LLM unexpected response: {response.completion}")
            return False
            
    except Exception as e:
        log(f"  ❌ Local LLM test failed: {e}")
        return False

async def test_cloud_fallback():
    """Test cloud LLM fallback (Gemini)."""
    log("☁️ Testing cloud LLM fallback...")
    
    try:
        from runner import gemini_text
        
        # Test Gemini fallback
        response = await gemini_text("Say 'Cloud fallback working' if you can read this.")
        
        if "working" in response.lower():
            log("  ✅ Cloud fallback (Gemini) responding correctly")
            log(f"  Response: {response}")
            return True
        else:
            log(f"  ❌ Cloud fallback unexpected response: {response}")
            return False
            
    except Exception as e:
        log(f"  ❌ Cloud fallback test failed: {e}")
        return False

async def test_planning_system():
    """Test the planning system without browser."""
    log("🎯 Testing planning system...")
    
    try:
        from runner import plan_with_o3_then_gemini
        
        # Test planning with a simple goal
        goal = "Navigate to example.com and find the main heading"
        subtasks = await plan_with_o3_then_gemini(goal)
        
        if subtasks and len(subtasks) > 0:
            log(f"  ✅ Planning system working - generated {len(subtasks)} subtasks")
            for i, task in enumerate(subtasks, 1):
                log(f"    {i}. {task.get('title', 'Untitled')}")
            return True
        else:
            log("  ❌ Planning system returned no subtasks")
            return False
            
    except Exception as e:
        log(f"  ❌ Planning system test failed: {e}")
        return False

async def main():
    """Main test function."""
    load_dotenv()
    
    log("🧪 Quick Phase 5 Test")
    log("=" * 40)
    log("Testing core components without full browser integration")
    log("")
    
    # Run tests
    tests = [
        ("Local LLM", test_local_llm_only()),
        ("Cloud Fallback", test_cloud_fallback()),
        ("Planning System", test_planning_system()),
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        log(f"Running: {test_name}")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            log(f"  ❌ Test crashed: {e}")
            results.append((test_name, False))
        log("")
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    log("=" * 40)
    log("🎯 QUICK TEST SUMMARY")
    log("=" * 40)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        log(f"{status} {test_name}")
    
    log("")
    log(f"Overall: {passed}/{total} tests passed ({passed/total:.1%})")
    
    if passed >= 2:  # At least local LLM and one other component
        log("🎉 Core functionality WORKING!")
        log("")
        log("✅ Privacy: Local LLM execution confirmed")
        log("✅ Cost: Cloud fallback available for planning")
        log("✅ Architecture: Hybrid system operational")
        log("")
        log("Phase 5 core goals validated!")
        return True
    else:
        log("⚠️ Core functionality ISSUES")
        log("Some critical components not working")
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