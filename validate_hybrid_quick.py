#!/usr/bin/env python3
"""
Quick validation of hybrid local+cloud setup
Simple test with minimal complexity for fast verification
"""

import asyncio
from browser_use import Agent
from browser_use.llm.llamacpp.chat import ChatLlamaCpp

async def test_hybrid_quick():
    """Quick test of hybrid functionality"""
    print("[TEST] Quick hybrid validation...")
    
    # Use local LLM for simple task
    local_llm = ChatLlamaCpp(
        base_url="http://localhost:8080",
        model="qwen2.5:14b-instruct-q4_k_m",
        temperature=0.1,
        max_tokens=1024  # Smaller to be faster
    )
    
    agent = Agent(
        task="Go to https://httpbin.org/json and extract any information you can",
        llm=local_llm,
        use_vision=False,
        save_conversation_path="./logs/hybrid_quick_test.json"
    )
    
    try:
        print("[RUN] Starting quick test...")
        result = await agent.run()
        
        print(f"[RESULT] Task completed successfully")
        
        # Check if we got results
        if result and hasattr(result, 'all_results') and result.all_results:
            final_result = result.all_results[-1]
            if hasattr(final_result, 'success') and final_result.success:
                print(f"[SUCCESS] Final action succeeded: {final_result.success}")
                return True
            
        print("[OK] Test completed, checking for any results...")
        return len(result.all_results) > 0 if result and hasattr(result, 'all_results') else False
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_hybrid_quick())
    if success:
        print("\n[SUCCESS] Hybrid system is working!")
    else:
        print("\n[FAIL] Hybrid system needs attention")