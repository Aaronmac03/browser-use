#!/usr/bin/env python3
"""Test vision with the exact same approach as our working direct test."""

import asyncio
import httpx
import base64
from PIL import Image
import io
import tempfile

async def test_vision_fixed():
    """Test vision with the working approach."""
    print("🧪 Testing vision with working approach...")
    
    # Create a tiny test image
    img = Image.new('RGB', (50, 50), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    print(f"📸 Created test image, base64 length: {len(image_b64)}")
    
    # Use the exact same payload as our working test
    payload = {
        "model": "moondream:latest",
        "prompt": "Describe this image briefly in JSON format: {\"caption\": \"description\", \"elements\": []}",
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 100
        }
    }
    
    try:
        print("🔍 Calling Ollama API...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json=payload
            )
            
            print(f"✅ Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                print(f"📝 Response: {response_text[:300]}")
                return True
            else:
                print(f"❌ Failed with status: {response.status_code}")
                print(f"📄 Error: {response.text[:300]}")
                return False
                
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_vision_fixed())
    exit(0 if success else 1)