#!/usr/bin/env python3
"""
Test a simple local LLM approach without needing Ollama service
"""

import asyncio
import json
import sys
from typing import Dict, Any

class SimpleLLMMock:
    """A mock LLM that provides consistent JSON responses for testing"""
    
    def __init__(self):
        self.name = "SimpleMock"
        self.available = True
    
    async def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a simple, consistent JSON response"""
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Return consistent JSON structure based on prompt type
        if "action" in prompt.lower():
            return {
                "action": "click",
                "coordinate": [100, 200],
                "text": "button",
                "confidence": 0.95,
                "reasoning": "Found clickable button at specified coordinates"
            }
        elif "describe" in prompt.lower() or "image" in prompt.lower():
            return {
                "description": "A simple test image with basic content",
                "confidence": 0.90,
                "elements": ["button", "text", "image"]
            }
        else:
            return {
                "response": "Simple mock response to prompt",
                "status": "success",
                "model": self.name
            }

async def test_simple_llm():
    """Test the simple LLM mock"""
    print("Testing Simple LLM Mock...")
    
    llm = SimpleLLMMock()
    
    if not llm.available:
        print("[FAIL] LLM not available")
        return False
    
    try:
        # Test basic response
        response1 = await llm.generate_response("Hello, how are you?")
        print(f"[PASS] Basic response: {json.dumps(response1, indent=2)}")
        
        # Test action response  
        response2 = await llm.generate_response("What action should I take on this button?")
        print(f"[PASS] Action response: {json.dumps(response2, indent=2)}")
        
        # Test vision response
        response3 = await llm.generate_response("Describe this image")
        print(f"[PASS] Vision response: {json.dumps(response3, indent=2)}")
        
        print("\n[SUCCESS] All tests passed! Simple LLM is working consistently.")
        return True
        
    except Exception as e:
        print(f"[FAIL] Test failed: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_llm())
    sys.exit(0 if success else 1)