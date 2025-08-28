#!/usr/bin/env python3
"""
Basic configuration test for Qwen2.5-VL integration.
Tests model configuration without external dependencies.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_model_config():
    """Test that our model configuration loads properly."""
    print("🤖 Testing Model Configuration")
    print("=" * 50)
    
    try:
        # Test basic imports
        print("📦 Testing imports...")
        from config.models import ModelConfigManager, TaskComplexity, ModelProvider
        print("✅ Model config imports successful")
        
        # Initialize manager
        print("\n🔧 Initializing ModelConfigManager...")
        manager = ModelConfigManager()
        print("✅ ModelConfigManager initialized")
        
        # Test Granite 3.2 Vision configuration
        print("\n🔍 Checking Granite 3.2 Vision configuration...")
        granite_config = manager.get_model_config("granite3.2-vision")
        if granite_config:
            print(f"✅ Granite 3.2 Vision found: {granite_config.name}")
            print(f"   Provider: {granite_config.provider}")
            print(f"   Model ID: {granite_config.model_id}")
            print(f"   Vision support: {granite_config.specs.supports_vision}")
            print(f"   Context length: {granite_config.specs.context_length}")
            print(f"   Memory requirement: {granite_config.specs.estimated_memory_gb}GB")
        else:
            print("❌ Granite 3.2 Vision configuration not found")
            return False
        
        # Test Gemini 2.5 Flash
        print("\n🔍 Checking Gemini 2.5 Flash configuration...")
        gemini_config = manager.get_model_config("gemini-2.5-flash")
        if gemini_config:
            print(f"✅ Gemini 2.5 Flash found: {gemini_config.name}")
            print(f"   Cost per 1K tokens: ${gemini_config.specs.cost_per_1k_tokens}")
        else:
            print("❌ Gemini 2.5 Flash configuration not found")
            return False
        
        # Test O3 Mini
        print("\n🔍 Checking OpenAI O3 Mini configuration...")
        o3_config = manager.get_model_config("o3-mini")
        if o3_config:
            print(f"✅ O3 Mini found: {o3_config.name}")
            print(f"   Context length: {o3_config.specs.context_length}")
        else:
            print("❌ O3 Mini configuration not found")
            return False
        
        # Test task presets (local-first)
        print("\n📋 Testing task complexity presets...")
        for complexity in TaskComplexity:
            models = manager.get_models_for_task(complexity)
            if models:
                primary_model = models[0]
                print(f"✅ {complexity.value}: {primary_model.name} ({primary_model.provider.value})")
                
                # Verify local-first approach
                if primary_model.name != "Granite 3.2 Vision":
                    print(f"⚠️  Warning: {complexity.value} doesn't use Granite 3.2 Vision as primary")
            else:
                print(f"❌ No models found for {complexity.value}")
                return False
        
        # Test local model filtering
        print("\n🏠 Testing local model filtering...")
        local_models = manager.list_models(provider=ModelProvider.OLLAMA)
        print(f"✅ Found {len(local_models)} local models:")
        for model in local_models:
            vision_status = "🔍" if model.specs.supports_vision else "📝"
            print(f"   {vision_status} {model.name}")
        
        print("\n🎉 All configuration tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_routing_strategy():
    """Test model router configuration."""
    print("\n🛤️  Testing Model Router")
    print("=" * 30)
    
    try:
        from models.model_router import ModelRouter, RoutingStrategy, TaskRequirements
        from config.models import ModelConfigManager
        
        # Initialize components
        manager = ModelConfigManager()
        router = ModelRouter(manager)
        
        print(f"✅ Router initialized with strategy: {router.default_strategy}")
        
        if router.default_strategy == RoutingStrategy.LOCAL_FIRST:
            print("✅ Local-first strategy confirmed")
        else:
            print(f"⚠️  Expected LOCAL_FIRST, got {router.default_strategy}")
        
        # Test fallback chains
        print("\n📊 Checking fallback chains...")
        for complexity, models in router._fallback_chains.items():
            primary = models[0] if models else "None"
            print(f"   {complexity.value}: {primary}")
            if primary != "granite3.2-vision":
                print(f"   ⚠️  Expected granite3.2-vision, got {primary}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Router import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Router error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Basic Configuration Tests")
    print("Testing local-first agent setup with Granite 3.2 Vision")
    print()
    
    success = True
    success &= test_model_config()
    success &= test_routing_strategy()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED - Configuration is ready!")
        print("\nNext steps:")
        print("1. Install Ollama: brew install ollama")
        print("2. Pull Granite Vision: ollama run granite3.2-vision")
        print("3. Set API keys for cloud models")
        exit(0)
    else:
        print("❌ SOME TESTS FAILED - Check configuration")
        exit(1)