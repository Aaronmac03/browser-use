#!/usr/bin/env python3
"""
Functional test for local-first browser agent with Granite 3.2 Vision.
Tests the model selection and basic agent functionality.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all components can be imported."""
    try:
        from config.models import ModelConfigManager, TaskComplexity, ModelCapability
        from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
        from models.local_handler import OllamaModelHandler
        from utils.serper import SerperAPI
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_model_selection():
    """Test model selection with different task requirements."""
    print("\n🤖 Testing Model Selection")
    print("=" * 40)
    
    try:
        from config.models import ModelConfigManager, TaskComplexity, ModelCapability
        from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
        
        # Initialize components
        manager = ModelConfigManager()
        router = ModelRouter(manager)
        
        # Test simple task - should use Granite 3.2 Vision
        simple_task = TaskRequirements(
            complexity=TaskComplexity.SIMPLE,
            requires_vision=True
        )
        
        selected_model = await router.select_model(simple_task)
        print(f"✅ Simple task: {selected_model.name}")
        
        # Test moderate task with vision
        moderate_task = TaskRequirements(
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            max_cost=0.01  # Force local models
        )
        
        selected_model = await router.select_model(moderate_task)
        print(f"✅ Moderate task: {selected_model.name}")
        
        # Test complex task 
        complex_task = TaskRequirements(
            complexity=TaskComplexity.COMPLEX,
            requires_vision=True,
            requires_code=True
        )
        
        selected_model = await router.select_model(complex_task)
        print(f"✅ Complex task: {selected_model.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model selection test failed: {e}")
        return False

async def test_ollama_connection():
    """Test connection to Ollama service."""
    print("\n🔌 Testing Ollama Connection")
    print("=" * 30)
    
    try:
        from models.local_handler import OllamaModelHandler
        
        handler = OllamaModelHandler()
        
        # Test basic connection
        models = await handler.list_models()
        print(f"✅ Connected to Ollama - found {len(models)} models")
        
        # Check if granite3.2-vision is available
        granite_info = await handler.get_model_info("granite3.2-vision")
        if granite_info:
            print("✅ Granite 3.2 Vision model available")
        else:
            print("⚠️  Granite 3.2 Vision model not found - may need to pull")
            
        # List available models
        if models:
            print("📋 Available models:")
            for model in models:
                print(f"   - {model.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ollama connection test failed: {e}")
        return False

async def test_serper_api():
    """Test Serper API functionality."""
    print("\n🔍 Testing Serper API")
    print("=" * 20)
    
    try:
        from utils.serper import SerperAPI
        
        # Initialize with test key (won't make real requests)
        api = SerperAPI(api_key="test-key")
        print("✅ Serper API initialized")
        
        # Test would require real API key for actual requests
        print("⚠️  Real API tests require SERPER_API_KEY environment variable")
        
        return True
        
    except Exception as e:
        print(f"❌ Serper API test failed: {e}")
        return False

async def test_hotel_search_workflow():
    """Test hotel search workflow components."""
    print("\n🏨 Testing Hotel Search Workflow")
    print("=" * 35)
    
    try:
        from config.models import ModelConfigManager, TaskComplexity
        from models.model_router import ModelRouter, TaskRequirements
        
        # Initialize components
        manager = ModelConfigManager()
        router = ModelRouter(manager)
        
        # Test task similar to Louisville Omni search
        hotel_task = TaskRequirements(
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,  # For analyzing hotel websites
            max_cost=0.05,  # Keep costs reasonable
        )
        
        selected_model = await router.select_model(hotel_task)
        print(f"✅ Hotel search would use: {selected_model.name}")
        print(f"   Provider: {selected_model.provider.value}")
        print(f"   Vision capable: {selected_model.specs.supports_vision}")
        print(f"   Estimated cost: {selected_model.specs.cost_per_1k_tokens or 'Free (local)'}")
        
        # Test escalation scenario
        complex_hotel_task = TaskRequirements(
            complexity=TaskComplexity.EXPERT,
            requires_vision=True,
            requires_code=True
        )
        
        escalated_model = await router.select_model(complex_hotel_task)
        print(f"✅ Complex hotel search would escalate to: {escalated_model.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Hotel search workflow test failed: {e}")
        return False

async def main():
    """Run all functional tests."""
    print("🧪 Functional Tests - Local-First Browser Agent")
    print("Primary Model: Granite 3.2 Vision")
    print("Escalation: Gemini 2.5 Flash → Claude 3.5 Sonnet → GPT-4o → O3 Mini")
    print("=" * 60)
    
    success = True
    
    # Test imports
    success &= test_imports()
    
    # Test async components
    success &= await test_model_selection()
    success &= await test_ollama_connection()
    success &= await test_serper_api()
    success &= await test_hotel_search_workflow()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL FUNCTIONAL TESTS PASSED!")
        print("\n🎯 Ready for E2E Testing:")
        print("1. Set SERPER_API_KEY for search optimization")
        print("2. Set GOOGLE_API_KEY for Gemini 2.5 Flash escalation")
        print("3. Run: python test_e2e_hotel_search.py")
    else:
        print("❌ SOME FUNCTIONAL TESTS FAILED")
        print("Check configuration and dependencies")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))