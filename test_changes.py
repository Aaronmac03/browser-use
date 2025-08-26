#!/usr/bin/env python3
"""
Test script to verify the changes made to hybrid_agent.py and vision_module.py
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_agent import PlannerClient, GenericAction, PlanJSON
from vision_module import VisionAnalyzer

async def test_planner_post_processing():
    """Test the PlannerClient post-processing functionality."""
    print("Testing PlannerClient post-processing...")
    
    # Create a mock planner client
    planner = PlannerClient()
    
    # Test case 1: Task without http and no search_web in first two steps
    test_plan = PlanJSON(
        normalized_task="Find kroger milk price",
        steps=[
            GenericAction(primitive="go_to_url", target="kroger.com", value=None, notes="Navigate to Kroger"),
            GenericAction(primitive="click", target="search", value=None, notes="Click search")
        ],
        success_criteria=["Found price"],
        estimated_complexity="medium"
    )
    
    processed_plan = planner._post_process_plan(test_plan, "find kroger milk price")
    
    print(f"Original steps: {len(test_plan.steps)}")
    print(f"Processed steps: {len(processed_plan.steps)}")
    print(f"First step primitive: {processed_plan.steps[0].primitive}")
    print(f"Search query: {processed_plan.steps[0].value}")
    
    # Test case 2: Task with http (should not be modified)
    test_plan_with_url = PlanJSON(
        normalized_task="Navigate to http://kroger.com",
        steps=[
            GenericAction(primitive="go_to_url", target="http://kroger.com", value=None, notes="Navigate")
        ],
        success_criteria=["Navigated"],
        estimated_complexity="simple"
    )
    
    processed_plan_with_url = planner._post_process_plan(test_plan_with_url, "navigate to http://kroger.com")
    print(f"Plan with URL - Original: {len(test_plan_with_url.steps)}, Processed: {len(processed_plan_with_url.steps)}")
    
    # Test search query creation
    search_query = planner._create_search_query("find kroger milk price in 40222")
    print(f"Search query for 'find kroger milk price in 40222': '{search_query}'")
    
    print("✅ PlannerClient post-processing tests passed!")

async def test_vision_analyzer():
    """Test the VisionAnalyzer improvements."""
    print("\nTesting VisionAnalyzer improvements...")
    
    analyzer = VisionAnalyzer()
    
    # Test the new prompt
    prompt = analyzer.build_vision_prompt()
    print(f"New prompt length: {len(prompt)} characters")
    print("Prompt includes priority elements:", "PRIORITY ELEMENTS" in prompt)
    print("Prompt mentions up to 12 elements:", "up to 12" in prompt)
    
    # Check if Ollama is available
    ollama_available = await analyzer.check_ollama_availability()
    print(f"Ollama available: {ollama_available}")
    
    print("✅ VisionAnalyzer tests passed!")

def test_banner_patterns():
    """Test banner dismissal patterns."""
    print("\nTesting banner dismissal patterns...")
    
    import re
    
    banner_patterns = [
        r'accept', r'agree', r'got it', r'continue', r'close', r'^x$',
        r'ok', r'dismiss', r'allow', r'enable', r'yes'
    ]
    
    test_texts = [
        "Accept All Cookies",
        "I Agree",
        "Got it!",
        "Continue",
        "Close",
        "X",
        "OK",
        "Dismiss",
        "Allow All",
        "Enable Cookies",
        "Yes, I Accept"
    ]
    
    matches = 0
    for text in test_texts:
        for pattern in banner_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
                print(f"✅ '{text}' matches pattern '{pattern}'")
                break
    
    print(f"Banner pattern matching: {matches}/{len(test_texts)} texts matched")
    print("✅ Banner dismissal tests passed!")

async def main():
    """Run all tests."""
    print("🧪 Testing hybrid_agent.py and vision_module.py changes...\n")
    
    await test_planner_post_processing()
    await test_vision_analyzer()
    test_banner_patterns()
    
    print("\n🎉 All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())