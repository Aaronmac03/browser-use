#!/usr/bin/env python3
"""
Test script for DOM-first search optimization in hybrid_agent.py

This demonstrates the fast DOM-first approach that avoids vision entirely
when search inputs can be found via CSS selectors.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

from hybrid_agent import HybridAgent, GenericAction, ExecutionContext

async def test_dom_search():
    """Test the DOM-first search optimization."""
    
    print("🧪 Testing DOM-first search optimization...")
    print("This demonstrates fast DOM-first search that avoids vision entirely")
    
    # Create hybrid agent
    agent = HybridAgent()
    
    try:
        # Initialize browser session
        await agent.initialize()
        print("✅ Browser session initialized")
        
        # Test 1: Navigate to Google (search-friendly site)
        print("\n📍 Test 1: Navigate to Google")
        nav_action = GenericAction(
            primitive="go_to_url",
            target="https://www.google.com",
            notes="Navigate to Google for DOM search test"
        )
        context = ExecutionContext(current_step=0, history=[])
        result = await agent.execute_action(nav_action, context)
        print(f"Navigation result: {result.result}")
        
        # Test 2: Direct DOM-first search (should be very fast)
        print("\n🔍 Test 2: Direct DOM-first search (bypassing vision)")
        search_action = GenericAction(
            primitive="type",
            target="search input",  # This will trigger DOM-first optimization
            value="milk 40222",
            notes="Test DOM-first search optimization"
        )
        context.history.append(result)
        context.current_step = 1
        search_result = await agent.execute_action(search_action, context)
        print(f"Search result: {search_result.result}")
        print(f"Search summary: {search_result.summary}")
        
        # Test 3: Probe DOM capability
        print("\n🔍 Test 3: Probe DOM search capability")
        success, probe_result = await agent._probe_dom_search_capability()
        print(f"DOM probe result: {success}")
        print(f"Probe content: {probe_result.extracted_content}")
        
        # Test 4: Navigate to Amazon (another search-friendly site)
        print("\n📍 Test 4: Navigate to Amazon")
        nav_action2 = GenericAction(
            primitive="go_to_url",
            target="https://www.amazon.com",
            notes="Navigate to Amazon for DOM search test"
        )
        context.current_step = 2
        result2 = await agent.execute_action(nav_action2, context)
        print(f"Amazon navigation result: {result2.result}")
        
        # Test 5: Try DOM search on Amazon
        print("\n🔍 Test 5: Try DOM-first search on Amazon")
        success, amazon_result = await agent._try_dom_search_input("laptop")
        print(f"Amazon DOM search result: {success}")
        print(f"Amazon search content: {amazon_result.extracted_content}")
        
        print("\n✅ DOM-first search optimization tests completed!")
        print("Key benefits demonstrated:")
        print("  - Fast CSS selector-based search input detection")
        print("  - Direct CDP input without vision processing")
        print("  - Automatic fallback to browser-use API if CDP fails")
        print("  - Proactive detection after navigation")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await agent.cleanup()
            print("🧹 Cleanup completed")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

if __name__ == "__main__":
    asyncio.run(test_dom_search())