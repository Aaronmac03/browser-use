#!/usr/bin/env python3
"""Simple test of the vision module with a tiny image."""

import asyncio
import tempfile
from PIL import Image
import base64
import io
from vision_module import VisionAnalyzer

async def test_vision():
    """Test vision with a tiny synthetic image."""
    print("🧪 Testing vision module with tiny image...")
    
    # Create a tiny test image (50x50 pixels)
    img = Image.new('RGB', (50, 50), color='white')
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        img.save(tmp.name, 'PNG')
        temp_path = tmp.name
    
    try:
        # Initialize vision analyzer
        analyzer = VisionAnalyzer()
        
        print(f"📸 Created test image: {temp_path}")
        print(f"🔍 Starting vision analysis...")
        
        # Test the analysis
        result = await analyzer.analyze(temp_path, "test://url", "Test Page")
        
        print(f"✅ Vision analysis completed!")
        print(f"📝 Caption: {result.caption}")
        print(f"🔢 Elements found: {len(result.elements)}")
        print(f"⚡ Model: {result.meta.model_name}")
        print(f"⏱️ Processing time: {result.meta.processing_time:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Vision test failed: {type(e).__name__}: {e}")
        return False
    
    finally:
        # Clean up
        import os
        try:
            os.unlink(temp_path)
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_vision())
    exit(0 if success else 1)