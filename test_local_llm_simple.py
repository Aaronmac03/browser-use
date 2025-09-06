#!/usr/bin/env python3
"""
Simple test to verify local LLM is working properly
"""

import asyncio
import sys
from pathlib import Path

# Add the browser-use directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm
from browser_use.llm.messages import SystemMessage, UserMessage

async def test_local_llm_direct():
    """Test local LLM directly without browser automation"""
    
    print("Testing local LLM directly...")
    
    try:
        llm = make_local_llm()
        print(f"Created LLM: {llm.model}")
        
        # Simple test
        messages = [
            SystemMessage(content="You are a helpful assistant. Respond briefly."),
            UserMessage(content="What is 2+2?")
        ]
        
        print("Sending simple math question...")
        result = await llm.ainvoke(messages)
        print(f"Response: {result.completion}")
        
        # Test with slightly more complex content
        messages2 = [
            SystemMessage(content="You are a web navigation assistant."),
            UserMessage(content="I need to navigate to kroger.com and search for milk. What should be my first action?")
        ]
        
        print("\nSending navigation question...")
        result2 = await llm.ainvoke(messages2)
        print(f"Response: {result2.completion}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_local_llm_with_large_context():
    """Test local LLM with larger context to see if it triggers 502 errors"""
    
    print("\nTesting local LLM with larger context...")
    
    try:
        llm = make_local_llm()
        
        # Create a larger context similar to what browser automation would send
        large_dom = "This is a simulated DOM content. " * 200  # ~6000 chars
        
        messages = [
            SystemMessage(content="You are a web automation agent. You can navigate websites and interact with elements."),
            UserMessage(content=f"Current page content:\n{large_dom}\n\nTask: Navigate to kroger.com. What action should I take?")
        ]
        
        print(f"Sending request with ~{len(str(messages))} characters...")
        result = await llm.ainvoke(messages)
        print(f"Response: {result.completion[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"Error with large context: {e}")
        return False

async def main():
    print("=" * 60)
    print("LOCAL LLM DIRECT TEST")
    print("=" * 60)
    
    # Test 1: Simple direct test
    success1 = await test_local_llm_direct()
    
    # Test 2: Large context test
    success2 = await test_local_llm_with_large_context()
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print(f"Simple test: {'PASS' if success1 else 'FAIL'}")
    print(f"Large context test: {'PASS' if success2 else 'FAIL'}")
    
    if success1 and success2:
        print("✅ Local LLM is working properly")
        print("❌ The 502 errors are likely due to browser automation context size")
    elif success1:
        print("⚠️ Local LLM works for simple requests but fails with large context")
        print("❌ Need to implement context size limiting")
    else:
        print("❌ Local LLM is not working at all")
        print("❌ Check llama.cpp server configuration")

if __name__ == "__main__":
    asyncio.run(main())