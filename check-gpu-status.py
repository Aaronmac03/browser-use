#!/usr/bin/env python3
"""
GPU Status Check for llama.cpp Server
Optimized for Windows PC Phase 3B deployment
"""

import asyncio
import httpx
import time
import subprocess

async def check_gpu_status():
    """Check if llama.cpp server is using GPU acceleration."""
    
    print("[INFO] Checking GPU acceleration status...")
    
    # Check NVIDIA GPU status
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu", 
             "--format=csv,noheader,nounits"], 
            capture_output=True, text=True, check=True
        )
        
        gpu_info = result.stdout.strip().split(', ')
        gpu_name = gpu_info[0]
        mem_used = int(gpu_info[1])
        mem_total = int(gpu_info[2])
        gpu_util = int(gpu_info[3])
        
        print(f"[GPU] {gpu_name}")
        print(f"[MEM] {mem_used}MB / {mem_total}MB ({mem_used/mem_total*100:.1f}%)")
        print(f"[UTIL] {gpu_util}% GPU utilization")
        
        if mem_used > 1000:  # More than 1GB used suggests model is loaded on GPU
            print("[SUCCESS] Model appears to be loaded on GPU")
            return True
        else:
            print("[WARN] Model may not be using GPU acceleration")
            
    except Exception as e:
        print(f"[ERROR] Could not check GPU status: {e}")
    
    # Check llama.cpp server status
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/props", timeout=5)
            if response.status_code == 200:
                props = response.json()
                print(f"[SERVER] Status: Running")
                
                # Look for GPU-related properties
                for key, value in props.items():
                    if 'gpu' in key.lower() or 'cuda' in key.lower():
                        print(f"[GPU-PROP] {key}: {value}")
                        
                return True
            else:
                print(f"[ERROR] Server responded with status {response.status_code}")
                
    except Exception as e:
        print(f"[ERROR] Could not connect to llama.cpp server: {e}")
    
    return False

async def performance_test():
    """Quick performance test to measure response time."""
    
    print("\n[TEST] Running performance test...")
    
    test_prompt = "Hello, how are you today?"
    
    try:
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8080/completion",
                json={
                    "prompt": test_prompt,
                    "max_tokens": 50,
                    "temperature": 0.1,
                    "stop": ["\n"]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                elapsed = time.time() - start_time
                result = response.json()
                
                print(f"[PERF] Response time: {elapsed:.2f}s")
                print(f"[PERF] Tokens generated: {result.get('tokens_predicted', 'N/A')}")
                
                if elapsed < 3.0:
                    print("[SUCCESS] Performance meets Phase 3B requirements (<3s)")
                else:
                    print("[WARN] Performance slower than target (3s)")
                    
            else:
                print(f"[ERROR] Test failed with status {response.status_code}")
                
    except Exception as e:
        print(f"[ERROR] Performance test failed: {e}")

if __name__ == "__main__":
    async def main():
        gpu_ok = await check_gpu_status()
        if gpu_ok:
            await performance_test()
        
        print("\n[SUMMARY] GPU status check complete")
    
    asyncio.run(main())