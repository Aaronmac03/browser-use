#!/usr/bin/env python3
"""Test local LLM connectivity and serialization."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_local_llm():
    """Test local LLM connectivity."""
    load_dotenv()
    
    try:
        from runner import make_local_llm
        from browser_use.llm.messages import UserMessage
        
        print("Creating local LLM client...")
        llm = make_local_llm()
        
        print("Testing simple message...")
        messages = [UserMessage(content="What is 2+2? Answer with just the number.")]
        
        response = await llm.ainvoke(messages)
        print(f"Response: {response.completion}")
        
        print("Testing with complex content...")
        complex_message = UserMessage(content=[
            {"type": "text", "text": "What is the capital of France? Answer briefly."}
        ])
        
        response2 = await llm.ainvoke([complex_message])
        print(f"Complex response: {response2.completion}")
        
        return True
        
    except Exception as e:
        print(f"Local LLM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_local_llm())
    sys.exit(0 if success else 1)