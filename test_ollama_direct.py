#!/usr/bin/env python3
"""Direct test of Ollama API to debug the timeout issue."""

import asyncio
import httpx
import json
import base64
from PIL import Image
import io

async def test_ollama_api():
    """Test Ollama API directly."""
    print("🔧 Testing Ollama API directly...")
    
    # Create a tiny test image
    img = Image.new('RGB', (50, 50), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    print(f"📸 Created test image, base64 length: {len(image_b64)}")
    
    # Test 1: Check if Ollama is responding
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            print(f"✅ Ollama API responding: {response.status_code}")
            data = response.json()
            print(f"📋 Available models: {[m['name'] for m in data.get('models', [])]}")
    except Exception as e:
        print(f"❌ Ollama API not responding: {e}")
        return False
    
    # Test 2: Simple text generation (no image)
    try:
        print("🧪 Testing simple text generation...")
        payload = {
            "model": "moondream:latest",
            "prompt": "Say hello",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 10
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json=payload
            )
            print(f"✅ Text generation: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"📝 Response: {result.get('response', 'No response')[:100]}")
    except Exception as e:
        print(f"❌ Text generation failed: {e}")
        return False
    
    # Test 3: Vision with image (our actual use case)
    try:
        print("🧪 Testing vision with image...")
        payload = {
            "model": "moondream:latest",
            "prompt": "Describe this image briefly.",
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 50
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json=payload
            )
            print(f"✅ Vision generation: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"📝 Vision response: {result.get('response', 'No response')[:200]}")
                return True
            else:
                print(f"❌ Vision failed with status: {response.status_code}")
                print(f"📄 Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Vision generation failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ollama_api())
    exit(0 if success else 1)