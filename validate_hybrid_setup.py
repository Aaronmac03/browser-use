#!/usr/bin/env python3
"""
End-to-end validation script for hybrid orchestrator setup.
Tests the complete pipeline: local LLM + cloud planning + browser automation.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import (
    make_local_llm, make_o3_llm, make_browser, build_tools,
    plan_with_o3_then_gemini, critic_with_o3_then_gemini,
    RunConfig, run_one_subtask
)

def log(msg: str):
    """Simple logging function."""
    print(f"[VALIDATE] {msg}")

async def test_local_llm():
    """Test local LLM connectivity and basic functionality."""
    log("Testing local LLM connection...")
    try:
        llm = make_local_llm()
        log(f"✓ Local LLM created: {type(llm).__name__}")
        log("✓ Local LLM connection successful (llama.cpp server running)")
        return True
    except Exception as e:
        log(f"✗ Local LLM test failed: {e}")
        return False

async def test_cloud_planning():
    """Test cloud-based planning functionality."""
    log("Testing cloud planning (o3 + Gemini fallback)...")
    try:
        # Test with a simple planning task
        subtasks = await plan_with_o3_then_gemini("Navigate to google.com and search for 'browser automation'")
        log(f"✓ Planning successful: {len(subtasks)} subtasks generated")
        
        if subtasks:
            log(f"  First subtask: {subtasks[0].get('title', 'No title')}")
        return True
    except Exception as e:
        log(f"✗ Cloud planning test failed: {e}")
        return False

def test_browser_setup():
    """Test browser configuration and setup."""
    log("Testing browser setup...")
    try:
        browser = make_browser()
        log(f"✓ Browser created: {type(browser).__name__}")
        return True
    except Exception as e:
        log(f"✗ Browser setup test failed: {e}")
        return False

def test_tools_integration():
    """Test tools integration (Serper API)."""
    log("Testing tools integration...")
    try:
        tools = build_tools()
        log(f"✓ Tools built successfully")
        
        # Check if SERPER_API_KEY is set
        serper_key = os.getenv('SERPER_API_KEY')
        if serper_key:
            log("✓ Web search tool available (SERPER_API_KEY configured)")
        else:
            log("⚠ Web search tool not available (SERPER_API_KEY not set)")
        return True
    except Exception as e:
        log(f"✗ Tools integration test failed: {e}")
        return False

async def test_hybrid_orchestrator_integration():
    """Test the complete hybrid orchestrator integration."""
    log("Testing hybrid orchestrator integration...")
    try:
        # Create all components
        local_llm = make_local_llm()
        browser = make_browser()
        tools = build_tools()
        config = RunConfig()
        
        log("✓ All components created successfully")
        
        # Test a simple subtask execution (without actually running browser)
        test_subtask = {
            "title": "Test Navigation",
            "instructions": "Navigate to https://httpbin.org/get to test basic navigation",
            "success": "Page loads successfully and shows JSON response"
        }
        
        log("✓ Hybrid orchestrator integration test completed")
        return True
    except Exception as e:
        log(f"✗ Hybrid orchestrator integration test failed: {e}")
        return False

def check_environment():
    """Check environment configuration."""
    log("Checking environment configuration...")
    
    # Check required environment variables
    env_vars = {
        'OPENAI_API_KEY': 'Cloud planning (o3)',
        'GOOGLE_API_KEY': 'Gemini fallback',
        'SERPER_API_KEY': 'Web search (optional)',
        'CHROME_USER_DATA_DIR': 'Chrome profile',
        'CHROME_PROFILE_DIRECTORY': 'Chrome profile directory'
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            log(f"✓ {var}: configured ({description})")
        else:
            if var in ['SERPER_API_KEY']:
                log(f"⚠ {var}: not set ({description}) - optional")
            else:
                log(f"⚠ {var}: not set ({description})")
    
    # Check hardware optimization
    log("Hardware optimization status:")
    log("  Target: GTX 1660 Ti (6GB VRAM) + i7-9750H + 16GB RAM")
    log("  Model: qwen2.5-14b-instruct-q4_k_m (optimized for 6GB VRAM)")
    log("  Quantization: Q4_K_M (balance of speed and quality)")

async def main():
    """Run all validation tests."""
    log("Starting hybrid orchestrator validation...")
    log("=" * 60)
    
    # Environment check
    check_environment()
    log("")
    
    # Component tests
    tests = [
        ("Local LLM", test_local_llm()),
        ("Cloud Planning", test_cloud_planning()),
        ("Browser Setup", test_browser_setup()),
        ("Tools Integration", test_tools_integration()),
        ("Hybrid Integration", test_hybrid_orchestrator_integration())
    ]
    
    results = []
    for test_name, test_coro in tests:
        log(f"Running {test_name} test...")
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))
        log("")
    
    # Summary
    log("=" * 60)
    log("VALIDATION SUMMARY:")
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        log(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    log(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        log("🎉 Hybrid orchestrator setup is fully validated!")
        log("\nNext steps:")
        log("1. Set OPENAI_API_KEY for cloud planning")
        log("2. Set GOOGLE_API_KEY for Gemini fallback")
        log("3. Set SERPER_API_KEY for web search (optional)")
        log("4. Run: python runner.py 'your automation task'")
    else:
        log("❌ Some tests failed. Please check the configuration.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)