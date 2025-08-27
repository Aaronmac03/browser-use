#!/usr/bin/env python3
"""
Test Phase 2 integration: VisionAnalyzer in HybridAgent
"""

import asyncio
from hybrid_agent import HybridAgent


async def test_hybrid_integration():
    """Test that HybridAgent works with integrated VisionAnalyzer."""
    print("🧪 Testing HybridAgent with VisionAnalyzer integration...")
    
    # Create hybrid agent
    agent = HybridAgent()
    
    try:
        # Test the integrated vision analyzer with a simple task
        print("🔄 Testing VisionAnalyzer integration via execute_task...")
        
        simple_task = "Go to google.com and take a screenshot"
        
        # Execute task through hybrid agent
        result = await agent.execute_task(simple_task)
        
        print(f"✅ Task execution result: {result.get('status', 'unknown')}")
        
        if result.get('status') in ['completed', 'partial']:
            print("✅ VisionAnalyzer integration successful!")
            print(f"   Final result: {result.get('final_result', 'N/A')}")
            return True
        else:
            print(f"❌ Task failed: {result.get('error', 'unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    finally:
        # Cleanup
        if agent.browser_session:
            await agent.browser_session.close()
        print("✅ Browser session closed")
    
    return False


if __name__ == "__main__":
    success = asyncio.run(test_hybrid_integration())
    exit(0 if success else 1)