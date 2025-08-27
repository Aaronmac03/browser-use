#!/usr/bin/env python3
"""Simple test to validate vision model timeout fixes."""

import asyncio
import tempfile
from PIL import Image
import base64
import io
from vision_module import VisionAnalyzer

async def test_vision():
    # Create a simple test image
    img = Image.new('RGB', (200, 100), color='white')
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        img.save(temp_file.name)
        temp_path = temp_file.name
    
    # Test vision analyzer
    analyzer = VisionAnalyzer()
    
    print("Testing vision analyzer with increased timeouts...")
    print(f"Read timeout: 20.0s (was 8.0s)")
    print(f"Circuit breaker: 5 failures (was 3)")
    
    try:
        result = await analyzer.analyze(temp_path)
        print(f"SUCCESS: Vision analysis completed")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_vision())
    exit(0 if success else 1)