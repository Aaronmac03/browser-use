#!/usr/bin/env python3
"""Test the hybrid agent with vision integration."""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid_agent import HybridAgent

async def test_hybrid_vision():
    """Test hybrid agent with a simple vision task."""
    print("🧪 Testing hybrid agent with vision integration...")
    
    try:
        # Initialize hybrid agent
        agent = HybridAgent()
        
        # Test a simple task that should trigger vision analysis
        task = "go to google.com and describe what you see"
        
        print(f"🎯 Task: {task}")
        print(f"🚀 Starting hybrid agent...")
        
        # Execute the task
        result = await agent.execute_task(task)
        
        print(f"✅ Task completed!")
        print(f"📝 Result: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Hybrid agent test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_hybrid_vision())
    exit(0 if success else 1)