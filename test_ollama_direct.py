#!/usr/bin/env python3
"""
Direct test of Ollama model performance.
"""

import asyncio
import time
import requests

def test_ollama_direct():
    """Test Ollama model directly without browser-use complexity."""
    
    print("🧪 Direct Ollama Model Test")
    print("=" * 30)
    
    # Test both models
    models = [
        "qwen2.5:7b-instruct-q4_k_m",
        "qwen2.5:14b-instruct-q4_k_m"
    ]
    
    for model_name in models:
        print(f"\n🤖 Testing {model_name}")
        print("-" * 30)
        
        try:
            # Simple test prompt
            prompt = "You are a web navigation assistant. Your task is to navigate to example.com. What would you do first? Keep your response short and focused."
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False
            }
            
            start_time = time.time()
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
            end_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Response time: {end_time - start_time:.2f}s")
                print(f"📝 Response: {result['response'][:200]}...")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test with different timeout settings
    print(f"\n🔧 Testing 14B model with extended timeout")
    print("-" * 30)
    
    try:
        prompt = "Navigate to walmart.com and find the store locator. What are the steps?"
        
        payload = {
            "model": "qwen2.5:14b-instruct-q4_k_m",
            "prompt": prompt,
            "stream": False
        }
        
        start_time = time.time()
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=180)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Extended timeout response time: {end_time - start_time:.2f}s")
            print(f"📝 Response: {result['response'][:300]}...")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
        
    except Exception as e:
        print(f"❌ Extended timeout error: {e}")

if __name__ == "__main__":
    test_ollama_direct()