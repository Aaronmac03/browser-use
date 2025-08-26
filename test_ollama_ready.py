#!/usr/bin/env python3
"""
Quick test to verify moondream:latest is working
"""

import asyncio
import base64
import httpx
import json

async def test_ollama():
    print("Testing Ollama moondream:latest model...")
    
    # Create a simple 1x1 test image
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    
    payload = {
        "model": "moondream:latest",
        "prompt": "Describe this image in one sentence.",
        "images": [tiny_png_b64],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1}
    }
    
    try:
        timeout_config = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            print("Sending test request...")
            response = await client.post(
                "http://localhost:11434/api/generate",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Model responded: {result.get('response', 'No response')}")
                return True
            else:
                print(f"HTTP Error {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ollama())
    if success:
        print("\nOllama with moondream:latest is ready for hybrid agent!")
    else:
        print("\nModel test failed - check Ollama setup")