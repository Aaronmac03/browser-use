#!/usr/bin/env python3
"""
Test script for the new llama.cpp integration
"""

import asyncio
import sys
from pathlib import Path

# Test imports
try:
    from browser_use.llm import ChatLlamaCpp
    print("+ ChatLlamaCpp import successful")
except ImportError as e:
    print(f"- Import failed: {e}")
    sys.exit(1)

try:
    from llama_cpp_manager import LlamaCppManager
    print("+ LlamaCppManager import successful")
except ImportError as e:
    print(f"- LlamaCppManager import failed: {e}")
    sys.exit(1)

try:
    from vision_module_llamacpp import VisionAnalyzer
    print("+ VisionAnalyzer (llama.cpp) import successful")
except ImportError as e:
    print(f"- VisionAnalyzer import failed: {e}")
    sys.exit(1)


async def test_manager():
    """Test the LlamaCppManager functionality"""
    print("\n=== Testing LlamaCppManager ===")
    
    manager = LlamaCppManager()
    
    # Test server status check (without running server)
    status = await manager.check_server_status()
    print(f"Server status: running={status.running}, endpoint={status.endpoint}")
    
    if not status.running:
        print("Server not running (expected for this test)")
    
    return True


async def test_chat_model():
    """Test the ChatLlamaCpp model (without running server)"""
    print("\n=== Testing ChatLlamaCpp Model ===")
    
    # Test initialization
    llm = ChatLlamaCpp(model="moondream2", host="http://localhost:8080")
    print(f"Model initialized: {llm.name}, provider: {llm.provider}")
    
    # Test client creation
    client = llm.get_client()
    print(f"HTTP client created: {type(client).__name__}")
    
    return True


async def test_vision_analyzer():
    """Test the VisionAnalyzer (without running server)"""
    print("\n=== Testing VisionAnalyzer ===")
    
    analyzer = VisionAnalyzer()
    print(f"Analyzer initialized with endpoint: {analyzer.endpoint}")
    
    # Test availability check (will fail without server, but shouldn't crash)
    try:
        available = await analyzer.check_server_availability()
        print(f"Server availability check completed: {available}")
    except Exception as e:
        print(f"Availability check failed (expected): {e}")
    
    return True


async def main():
    """Run all tests"""
    print("Testing llama.cpp Integration")
    print("=" * 40)
    
    tests = [
        test_manager,
        test_chat_model,
        test_vision_analyzer,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
                print(f"+ {test.__name__} passed")
            else:
                failed += 1
                print(f"- {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"- {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 40)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All integration tests passed!")
        print("\nNext steps:")
        print("1. Run: python setup_llamacpp.py")
        print("2. Start server: ./run_llamacpp_server.sh")
        print("3. Test with actual server: python llama_cpp_manager.py --test")
        return True
    else:
        print("Some tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)