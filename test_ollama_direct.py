#!/usr/bin/env python3
"""
Direct test of Ollama API with MiniCPM-V
"""

import asyncio
import httpx
import base64
import json
from pathlib import Path
from PIL import Image, ImageDraw

async def resolve_minicpm_tag(endpoint: str = "http://localhost:11434") -> str:
    """
    Resolve MiniCPM-V tag by querying Ollama API to avoid hardcoded :latest.
    
    Returns:
        str: Resolved model tag (e.g., 'minicpm-v')
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            if response.status_code == 200:
                data = response.json()
                # Find minicpm model
                for model in data.get('models', []):
                    model_name = model.get('name', '')
                    if 'minicpm-v' in model_name.lower():
                        # Return without :latest suffix
                        return model_name.replace(':latest', '')
                # Fallback if not found
                return "minicpm-v"
            else:
                return "minicpm-v"  # Default fallback
    except Exception:
        return "minicpm-v"  # Default fallback

async def test_ollama_api():
    """Test Ollama API directly."""
    
    # Create a simple test image
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Hello World", fill='black')
    draw.rectangle([50, 100, 300, 130], outline='blue', width=2)
    draw.text((60, 105), "Test Button", fill='blue')
    
    # Save to temp file and encode
    img.save('temp_test.png')
    with open('temp_test.png', 'rb') as f:
        image_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    print(f"🖼️ Image encoded: {len(image_b64)} chars")
    
    # Test basic connectivity first
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("🔗 Testing basic connectivity...")
            response = await client.get("http://localhost:11434/api/tags")
            print(f"✅ Connection OK: {response.status_code}")
            print(f"📋 Available models: {response.text[:200]}")
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
        
        # Test vision model
        print("\n🔍 Testing vision model...")
        model_tag = await resolve_minicpm_tag()
        print(f"🏷️ Using model tag: {model_tag}")
        
        payload = {
            "model": model_tag,
            "prompt": "Analyze this image and return JSON with: {\"description\": \"what you see\", \"elements\": [\"list of UI elements\"]}",
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1}
        }
        
        try:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=60.0
            )
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"📄 Response: {result.get('response', 'No response')[:300]}...")
                return True
            else:
                print(f"❌ Error response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Vision test failed: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_ollama_api())
    if success:
        print("\n🎉 Ollama API test passed!")
    else:
        print("\n💥 Ollama API test failed!")