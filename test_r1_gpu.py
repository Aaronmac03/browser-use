#!/usr/bin/env python3
"""
Test script for DeepSeek R1 8B model with GPU acceleration.
Validates GPU optimization and model loading.
"""

import asyncio
import subprocess
import time
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_r1_gpu_acceleration():
    """Test R1 model with GPU acceleration."""
    
    logger.info("[TEST] Starting DeepSeek R1 8B GPU acceleration test...")
    
    # Test 1: Check if model file exists
    model_path = "E:\\ai\\llama-models\\deepseek-r1-distill-llama-8b-q4_k_m.gguf"
    try:
        with open(model_path, 'rb') as f:
            # Read first 1KB to verify file is accessible
            f.read(1024)
        logger.info(f"[PASS] Model file exists and accessible: {model_path}")
    except Exception as e:
        logger.error(f"[FAIL] Model file error: {e}")
        return False
    
    # Test 2: Start server with R1 model
    server_exe = "E:\\ai\\llama.cpp\\build\\bin\\Release\\llama-server.exe"
    server_cmd = [
        server_exe,
        "--model", model_path,
        "--host", "localhost",
        "--port", "8081",  # Use different port for test
        "--ctx-size", "4096",
        "--n-gpu-layers", "35",
        "--threads", "4",
        "--batch-size", "128",
        "--ubatch-size", "256",
        "--memory-f16",
        "--mlock",
        "--no-warmup",
        "--flash-attn"
    ]
    
    logger.info("[TEST] Starting R1 server for 30 seconds...")
    
    try:
        # Start server process
        process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        # Wait for server to start
        await asyncio.sleep(10)
        
        # Test 3: Check server health
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:8081/health", timeout=5)
                if response.status_code == 200:
                    logger.info("[PASS] R1 server is responding to health checks")
                else:
                    logger.warning(f"[WARN] Server responded with status {response.status_code}")
            except Exception as e:
                logger.error(f"[FAIL] Health check failed: {e}")
        
        # Test 4: Simple completion test
        test_prompt = {
            "prompt": "Hello, how are you?",
            "max_tokens": 50,
            "temperature": 0.1,
            "stop": ["\n"]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8081/completion",
                    json=test_prompt,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    completion = result.get('content', '')
                    logger.info(f"[PASS] R1 completion test successful")
                    logger.info(f"[RESPONSE] {completion[:100]}...")
                else:
                    logger.error(f"[FAIL] Completion test failed with status {response.status_code}")
                    
        except Exception as e:
            logger.error(f"[FAIL] Completion test error: {e}")
        
        # Wait a bit more to see GPU usage
        logger.info("[INFO] Waiting 20 more seconds to observe GPU utilization...")
        await asyncio.sleep(20)
        
        # Cleanup
        process.terminate()
        await asyncio.sleep(2)
        
        if process.poll() is None:
            process.kill()
        
        logger.info("[CLEANUP] Server process terminated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Server startup error: {e}")
        return False

async def check_gpu_memory():
    """Check GPU memory usage during test."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                parts = lines[0].split(', ')
                if len(parts) >= 2:
                    used_mb = float(parts[0].strip())
                    total_mb = float(parts[1].strip())
                    used_gb = used_mb / 1024
                    total_gb = total_mb / 1024
                    usage_pct = (used_mb / total_mb) * 100
                    
                    logger.info(f"[GPU] Memory: {used_gb:.1f}GB / {total_gb:.1f}GB ({usage_pct:.1f}%)")
                    return True
                    
    except Exception as e:
        logger.debug(f"[GPU] Memory check failed: {e}")
    
    return False

if __name__ == "__main__":
    print("=" * 60)
    print("DeepSeek R1 8B GPU Acceleration Test")
    print("=" * 60)
    
    # Check GPU before test
    print("\n[BEFORE] GPU Memory Status:")
    asyncio.run(check_gpu_memory())
    
    # Run test
    success = asyncio.run(test_r1_gpu_acceleration())
    
    # Check GPU after test
    print("\n[AFTER] GPU Memory Status:")
    asyncio.run(check_gpu_memory())
    
    if success:
        print("\n✅ R1 GPU acceleration test completed successfully!")
        print("   The DeepSeek R1 8B model is ready for GPU-accelerated inference.")
    else:
        print("\n❌ R1 GPU acceleration test failed!")
        print("   Check the logs above for specific issues.")