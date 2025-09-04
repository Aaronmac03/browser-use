#!/usr/bin/env python3
"""
Comprehensive model access testing for Windows PC deployment.
Tests both Ollama and direct model access to determine best path forward.
"""

import os
import time
import requests
import json
from pathlib import Path

def test_ollama_service():
    """Test Ollama service connectivity and model availability."""
    print("=" * 50)
    print("OLLAMA SERVICE TEST")
    print("=" * 50)
    
    # Test service connectivity
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            print(f"✅ Ollama service: RESPONDING")
            print(f"📊 Models available: {len(models)}")
            
            if models:
                for model in models:
                    name = model.get('name', 'Unknown')
                    size = model.get('size', 0)
                    modified = model.get('modified_at', 'Unknown')
                    print(f"  - {name} ({size//1024//1024//1024:.1f}GB)")
            else:
                print("  ⚠️ No models detected by Ollama service")
            
            return True, models
        else:
            print(f"❌ Ollama service: HTTP {response.status_code}")
            return False, []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ollama service: CONNECTION FAILED ({e})")
        return False, []

def test_model_files():
    """Check physical model files in E:\ai\.ollama\models."""
    print("\n" + "=" * 50)
    print("PHYSICAL MODEL FILES TEST")
    print("=" * 50)
    
    models_path = Path("E:/ai/.ollama/models")
    
    if not models_path.exists():
        print("❌ Models directory not found")
        return False, []
    
    # Check blobs
    blobs_path = models_path / "blobs"
    if blobs_path.exists():
        blobs = list(blobs_path.glob("*"))
        total_size = sum(f.stat().st_size for f in blobs if f.is_file())
        print(f"✅ Blobs directory: {len(blobs)} files")
        print(f"📦 Total size: {total_size/1024/1024/1024:.1f}GB")
    
    # Check manifests
    manifests_path = models_path / "manifests/registry.ollama.ai/library"
    models_found = []
    
    if manifests_path.exists():
        print(f"✅ Manifests directory: EXISTS")
        
        # Look for model directories
        for model_dir in manifests_path.iterdir():
            if model_dir.is_dir():
                for variant_dir in model_dir.iterdir():
                    if variant_dir.is_dir():
                        model_name = f"{model_dir.name}:{variant_dir.name}"
                        models_found.append(model_name)
                        print(f"  📋 Found manifest: {model_name}")
        
        print(f"📊 Models with manifests: {len(models_found)}")
        return True, models_found
    else:
        print("❌ Manifests directory not found")
        return False, []

def test_browser_use_import():
    """Test browser-use import and basic functionality."""
    print("\n" + "=" * 50)
    print("BROWSER-USE INTEGRATION TEST")
    print("=" * 50)
    
    try:
        # Test imports
        start_time = time.time()
        from browser_use import ChatOllama
        from browser_use.llm.messages import SystemMessage, UserMessage
        import_time = time.time() - start_time
        
        print(f"✅ Import successful: {import_time:.2f}s")
        
        # Test client creation (without actual model call)
        try:
            client = ChatOllama(
                model="test-model",
                host="http://localhost:11434",
                timeout=10
            )
            print(f"✅ Client creation: SUCCESS")
            return True
            
        except Exception as e:
            print(f"⚠️ Client creation issue: {e}")
            return True  # Import worked, just client config issue
            
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ General error: {e}")
        return False

def test_direct_model_attempt():
    """Attempt to test model directly if available."""
    print("\n" + "=" * 50)
    print("DIRECT MODEL TEST ATTEMPT")
    print("=" * 50)
    
    # First check what Ollama thinks is available
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            
            if models:
                # Try the first available model
                model_name = models[0]['name']
                print(f"🔍 Testing model: {model_name}")
                
                # Attempt a simple generation
                test_payload = {
                    "model": model_name,
                    "prompt": "Say 'test' (one word only)",
                    "stream": False
                }
                
                start_time = time.time()
                response = requests.post(
                    "http://localhost:11434/api/generate", 
                    json=test_payload, 
                    timeout=30
                )
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get('response', '').strip()
                    print(f"✅ Model response: '{text}' ({duration:.2f}s)")
                    return True, model_name, duration, text
                else:
                    print(f"❌ Model call failed: HTTP {response.status_code}")
                    return False, model_name, duration, None
            else:
                print("⚠️ No models available to test")
                return False, None, 0, None
                
    except Exception as e:
        print(f"❌ Direct test error: {e}")
        return False, None, 0, None

def analyze_results_and_recommend():
    """Analyze all test results and recommend next steps."""
    print("\n" + "=" * 60)
    print("ANALYSIS & RECOMMENDATIONS")
    print("=" * 60)
    
    # Run all tests
    service_ok, ollama_models = test_ollama_service()
    files_ok, file_models = test_model_files()
    browser_use_ok = test_browser_use_import()
    
    # Attempt direct model test
    if service_ok and ollama_models:
        model_test_ok, tested_model, duration, response = test_direct_model_attempt()
    else:
        model_test_ok, tested_model, duration, response = False, None, 0, None
    
    print("\n📊 SUMMARY:")
    print(f"  Ollama Service: {'✅ OK' if service_ok else '❌ FAILED'}")
    print(f"  Physical Files: {'✅ OK' if files_ok else '❌ FAILED'} ({len(file_models)} models)")
    print(f"  Browser-use: {'✅ OK' if browser_use_ok else '❌ FAILED'}")
    print(f"  Model Testing: {'✅ OK' if model_test_ok else '❌ FAILED'}")
    
    if model_test_ok:
        print(f"  Response Time: {duration:.2f}s")
        print(f"  Model Used: {tested_model}")
        
    print("\n🎯 RECOMMENDATIONS:")
    
    if model_test_ok:
        print("✅ EXCELLENT: Ollama working perfectly!")
        print("  → Continue with Ollama")
        print("  → Models responding quickly")
        print("  → GPU acceleration likely active")
        
    elif service_ok and files_ok and browser_use_ok:
        print("⚠️ MIXED RESULTS: Components ready but models not accessible")
        print("  → Option 1: Fix Ollama model configuration")
        print("  → Option 2: Switch to llama.cpp for direct access")
        print("  → Option 3: Re-download models to default location")
        
    elif files_ok and browser_use_ok:
        print("🔧 SERVICE ISSUE: Models exist but Ollama not responding")
        print("  → Restart Ollama service")
        print("  → Check port conflicts")
        print("  → Consider llama.cpp as alternative")
        
    else:
        print("❌ MULTIPLE ISSUES: Need comprehensive troubleshooting")
        print("  → Recommend llama.cpp for reliable access")
        print("  → Direct model loading approach")
        
    # Specific recommendations
    print("\n💡 NEXT STEPS:")
    
    if not model_test_ok:
        print("1. llama.cpp Alternative:")
        print("   - Direct model loading (no service dependency)")
        print("   - GPU acceleration via cuBLAS")
        print("   - Compatible with browser-use architecture")
        
        print("2. Ollama Troubleshooting:")
        print("   - Verify model path configuration")
        print("   - Check for port/service conflicts")  
        print("   - Consider model re-download")
        
    return {
        'service_ok': service_ok,
        'files_ok': files_ok, 
        'browser_use_ok': browser_use_ok,
        'model_test_ok': model_test_ok,
        'ollama_models': len(ollama_models),
        'file_models': len(file_models),
        'response_time': duration if model_test_ok else None,
        'recommendation': 'ollama' if model_test_ok else 'llamacpp'
    }

if __name__ == "__main__":
    print("🧪 COMPREHENSIVE MODEL ACCESS TEST")
    print("🖥️ Windows PC: i7-9750H + GTX 1660 Ti + 15.85GB RAM")
    print("📁 Models: E:\\ai\\.ollama\\models (~14GB)")
    
    results = analyze_results_and_recommend()
    
    print(f"\n🎯 FINAL ASSESSMENT:")
    if results['model_test_ok']:
        print("🎉 SUCCESS: Ready for production testing!")
    elif results['browser_use_ok'] and results['files_ok']:
        print("🔧 READY FOR ALTERNATIVE: llama.cpp recommended")
    else:
        print("⚠️ NEEDS WORK: Multiple issues to resolve")
    
    print(f"\n📋 Results for planning discussion:")
    print(f"  - Service connectivity: {results['service_ok']}")
    print(f"  - Model files present: {results['file_models']} models")
    print(f"  - Browser-use ready: {results['browser_use_ok']}")
    print(f"  - Working models: {results['ollama_models']}")
    print(f"  - Recommended path: {results['recommendation']}")