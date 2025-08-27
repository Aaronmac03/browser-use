"""
Test script to verify hybrid agent integration points.

This validates that the key components work together without running a full browser session.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

async def test_imports():
    """Test that all hybrid imports work correctly."""
    print("Testing hybrid imports...")
    
    try:
        # Test hybrid component imports
        from hybrid.handoff_manager import HandoffManager
        from hybrid.vision_state_builder import VisionStateBuilder
        from hybrid.local_action_heuristics import LocalActionHeuristics
        from hybrid.cloud_planner_client import CloudPlannerClient
        from hybrid.schemas import VisionState, Action, ActionTarget
        print("✅ Hybrid component imports successful")
        
        # Test hybrid agent imports
        import hybrid_agent
        from hybrid_agent import (
            HybridAgentWrapper,
            check_ollama_availability,
            TaskRouter,
            structured_chat
        )
        print("✅ Hybrid agent imports successful")
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

async def test_ollama_connection():
    """Test connection to Ollama server."""
    print("\nTesting Ollama connection...")
    
    try:
        from hybrid_agent import check_ollama_availability
        is_available = await check_ollama_availability()
        
        if is_available:
            print("✅ Ollama is running and MiniCPM-V is available")
        else:
            print("⚠️  Ollama not available (will use fallback mode)")
        
        return is_available
    except Exception as e:
        print(f"❌ Ollama test error: {e}")
        return False

async def test_hybrid_components():
    """Test instantiation of hybrid components."""
    print("\nTesting hybrid component instantiation...")
    
    try:
        from hybrid.vision_state_builder import VisionStateBuilder
        from hybrid.local_action_heuristics import LocalActionHeuristics
        from hybrid.cloud_planner_client import CloudPlannerClient
        from hybrid.handoff_manager import HandoffManager
        
        # Test VisionStateBuilder
        vision_builder = VisionStateBuilder(
            ollama_base_url="http://localhost:11434",
            model_name="minicpm-v:2.6",
            confidence_threshold=0.7
        )
        print("✅ VisionStateBuilder created")
        
        # Test LocalActionHeuristics
        local_heuristics = LocalActionHeuristics(
            confidence_threshold=0.8,
            similarity_threshold=0.8
        )
        print("✅ LocalActionHeuristics created")
        
        # Test CloudPlannerClient (requires API key)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            cloud_client = CloudPlannerClient(
                api_key=google_api_key,
                model_name="gemini-2.0-flash-exp"
            )
            print("✅ CloudPlannerClient created")
        else:
            print("⚠️  GOOGLE_API_KEY not found, CloudPlannerClient not tested")
        
        # Test HandoffManager
        if google_api_key:
            handoff_manager = HandoffManager(
                vision_builder=vision_builder,
                local_heuristics=local_heuristics,
                cloud_client=cloud_client
            )
            print("✅ HandoffManager created")
        else:
            print("⚠️  HandoffManager not tested (missing API key)")
        
        return True
    except Exception as e:
        print(f"❌ Component instantiation error: {e}")
        return False

async def test_task_classification():
    """Test the task classification system."""
    print("\nTesting task classification...")
    
    try:
        from hybrid_agent import TaskRouter
        from browser_use.llm import ChatOpenAI
        
        # Check if OpenAI API key is available
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  OPENAI_API_KEY not found, skipping task classification test")
            return True
        
        llm = ChatOpenAI(model="gpt-4o-mini")
        
        # Test simple navigation task
        task_type = await TaskRouter.classify_task(llm, "Go to google.com")
        print(f"✅ Navigation task classified: {task_type.category} ({task_type.complexity})")
        
        # Test data extraction task  
        task_type = await TaskRouter.classify_task(llm, "Extract the table data from this page")
        print(f"✅ Data extraction task classified: {task_type.category} ({task_type.complexity})")
        
        return True
    except Exception as e:
        print(f"❌ Task classification error: {e}")
        return False

async def test_configuration():
    """Test configuration and environment setup."""
    print("\nTesting configuration...")
    
    # Check required environment variables
    required_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    optional_keys = ["GOOGLE_API_KEY", "SERPER_API_KEY"]
    
    for key in required_keys:
        if os.getenv(key):
            print(f"✅ {key} found")
        else:
            print(f"❌ {key} missing (required)")
    
    for key in optional_keys:
        if os.getenv(key):
            print(f"✅ {key} found")
        else:
            print(f"⚠️  {key} missing (optional)")
    
    # Test hybrid configuration
    from hybrid_agent import (
        USE_HYBRID_VISION,
        OLLAMA_URL, 
        MINICPM_MODEL,
        VISION_CONFIDENCE_THRESHOLD,
        LOCAL_ACTION_CONFIDENCE
    )
    
    print(f"✅ Hybrid configuration loaded:")
    print(f"   USE_HYBRID_VISION: {USE_HYBRID_VISION}")
    print(f"   OLLAMA_URL: {OLLAMA_URL}")
    print(f"   MINICPM_MODEL: {MINICPM_MODEL}")
    print(f"   VISION_CONFIDENCE_THRESHOLD: {VISION_CONFIDENCE_THRESHOLD}")
    print(f"   LOCAL_ACTION_CONFIDENCE: {LOCAL_ACTION_CONFIDENCE}")
    
    return True

async def main():
    """Run all integration tests."""
    print("🚀 Hybrid Agent Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Ollama Connection", test_ollama_connection),
        ("Component Instantiation", test_hybrid_components),
        ("Task Classification", test_task_classification),
        ("Configuration Check", test_configuration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        emoji = "✅" if result else "❌"
        print(f"{emoji} {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Hybrid agent is ready to use.")
    elif passed >= len(results) * 0.8:
        print("⚠️  Most tests passed. Hybrid agent should work with some limitations.")
    else:
        print("❌ Multiple test failures. Please check configuration and dependencies.")
    
    print("\nTo run the hybrid agent: python hybrid_agent.py")

if __name__ == "__main__":
    asyncio.run(main())