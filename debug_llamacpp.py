#!/usr/bin/env python3
"""Debug script for ChatLlamaCpp interface."""

import asyncio
import logging
from browser_use.llm.llamacpp.chat import ChatLlamaCpp
from browser_use.llm.messages import UserMessage

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_llamacpp():
    """Test ChatLlamaCpp interface directly."""
    print("Testing ChatLlamaCpp interface...")
    
    # Create ChatLlamaCpp instance
    llm = ChatLlamaCpp(
        model="qwen2.5-7b-instruct-q4_k_m.gguf",
        base_url="http://localhost:8080",
        temperature=0.1,
        max_tokens=50,
        timeout=60.0
    )
    
    # Create test message
    messages = [UserMessage(content="What is 2+2? Please respond with just the number.")]
    
    try:
        print("Sending request to ChatLlamaCpp...")
        result = await llm.ainvoke(messages)
        print(f"Success! Response: {result.completion}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_llamacpp())
    print(f"Test {'PASSED' if success else 'FAILED'}")