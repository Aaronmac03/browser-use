#!/usr/bin/env python3
"""
Test script for VisionStateBuilder with MiniCPM-V 2.6
"""

import asyncio
import tempfile
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys

# Add the current directory to sys.path so we can import hybrid_agent
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_agent import VisionStateBuilder, resolve_minicpm_tag

async def create_test_screenshot():
    """Create a simple test screenshot with some UI elements."""
    # Create a simple test image with UI elements
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a standard font, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        big_font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
        big_font = ImageFont.load_default()
    
    # Draw a simple login form
    # Title
    draw.text((300, 50), "Login Page", font=big_font, fill='black')
    
    # Email field
    draw.rectangle([200, 150, 600, 180], outline='gray', width=2)
    draw.text((210, 155), "Email", font=font, fill='gray')
    
    # Password field  
    draw.rectangle([200, 200, 600, 230], outline='gray', width=2)
    draw.text((210, 205), "Password", font=font, fill='gray')
    
    # Login button
    draw.rectangle([200, 260, 300, 290], fill='blue', outline='blue')
    draw.text((230, 268), "Login", font=font, fill='white')
    
    # Register link
    draw.text((350, 268), "Register", font=font, fill='blue')
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(temp_file.name)
    return temp_file.name

async def test_vision_state_builder():
    """Test the VisionStateBuilder with a sample screenshot."""
    print("🧪 Testing VisionStateBuilder with MiniCPM-V 2.6...")
    
    # Create test screenshot
    screenshot_path = await create_test_screenshot()
    print(f"📸 Created test screenshot: {screenshot_path}")
    
    try:
        # Resolve model tag first
        model_tag = await resolve_minicpm_tag()
        print(f"🏷️ Using model tag: {model_tag}")
        
        # Initialize vision builder
        vision_builder = VisionStateBuilder(
            model_endpoint="http://localhost:11434",
            model_name=model_tag
        )
        
        print("🔍 Analyzing screenshot with MiniCPM-V...")
        
        # Build vision state
        vision_state = await vision_builder.build_vision_state(
            screenshot_path=screenshot_path,
            page_url="http://example.com/login",
            page_title="Test Login Page"
        )
        
        print("\n✅ Vision analysis completed!")
        print(f"📝 Caption: {vision_state.caption}")
        print(f"🔢 Elements found: {len(vision_state.elements)}")
        print(f"📋 Fields found: {len(vision_state.fields)}")
        print(f"🎯 Affordances found: {len(vision_state.affordances)}")
        
        # Show details
        if vision_state.elements:
            print("\n🔍 Elements:")
            for i, elem in enumerate(vision_state.elements[:3]):  # Show first 3
                print(f"  {i+1}. {elem.role}: '{elem.visible_text}' (confidence: {elem.confidence:.2f})")
        
        if vision_state.fields:
            print("\n📝 Fields:")
            for i, field in enumerate(vision_state.fields[:3]):  # Show first 3
                print(f"  {i+1}. {field.name_hint}: '{field.value_hint}' (editable: {field.editable})")
                
        if vision_state.affordances:
            print("\n🎯 Affordances:")
            for i, afford in enumerate(vision_state.affordances[:3]):  # Show first 3
                print(f"  {i+1}. {afford.type}: '{afford.label}'")
                
        print(f"\n🌐 Page info: {vision_state.meta.url}")
        print(f"📑 Title: {vision_state.meta.title}")
        
        return True
        
    except Exception as e:
        print(f"❌ Vision analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temp file
        try:
            os.unlink(screenshot_path)
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_vision_state_builder())
    if success:
        print("\n🎉 VisionStateBuilder test passed!")
    else:
        print("\n💥 VisionStateBuilder test failed!")
        sys.exit(1)