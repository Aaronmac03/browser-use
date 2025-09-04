#!/usr/bin/env python3
"""
Performance optimization tests for GTX 1660 Ti hardware.
Tests GPU acceleration, memory usage, and response times.
"""

import asyncio
import logging
import time
import psutil
import pytest
from pathlib import Path

from enhanced_local_llm import OptimizedLocalLLM, LocalLLMConfig, PerformanceMonitor
from hybrid_orchestrator import HybridOrchestrator, HybridConfig

logger = logging.getLogger(__name__)

class PerformanceTestSuite:
    """Test suite for performance optimization validation."""
    
    def __init__(self):
        self.config = LocalLLMConfig()
        self.local_llm = OptimizedLocalLLM(self.config)
        self.performance_monitor = PerformanceMonitor()
        
    async def test_gpu_acceleration_enabled(self):
        """Test that GPU acceleration is properly configured."""
        logger.info("[TEST] Testing GPU acceleration configuration...")
        
        # Check if GPU layers are configured
        server_config_path = Path("e:/ai/start-llama-server.bat")
        if server_config_path.exists():
            content = server_config_path.read_text()
            
            # Should have GPU layers enabled for GTX 1660 Ti
            assert "--n-gpu-layers" in content, "GPU layers not configured"
            
            # Extract GPU layers value
            lines = content.split('\n')
            gpu_layers_line = [line for line in lines if "--n-gpu-layers" in line]
            if gpu_layers_line:
                # Should be > 0 for GPU acceleration
                gpu_layers = int(gpu_layers_line[0].split()[-1])
                logger.info(f"[GPU] Current GPU layers: {gpu_layers}")
                return gpu_layers
        
        return 0
    
    async def test_memory_optimization(self):
        """Test memory usage optimization for 16GB RAM system."""
        logger.info("[TEST] Testing memory optimization...")
        
        # Get current memory usage
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        
        logger.info(f"[MEMORY] Available RAM: {available_gb:.1f}GB")
        
        # Should have at least 4GB available for model loading
        assert available_gb >= 4.0, f"Insufficient RAM: {available_gb:.1f}GB available"
        
        # Test model loading memory impact
        start_memory = psutil.virtual_memory().used
        
        try:
            await self.local_llm.get_optimized_client()
            
            # Check memory increase (should be reasonable for 7B model)
            end_memory = psutil.virtual_memory().used
            memory_increase_gb = (end_memory - start_memory) / (1024**3)
            
            logger.info(f"[MEMORY] Model loading increased memory by: {memory_increase_gb:.1f}GB")
            
            # Should be less than 8GB for Q4_K_M quantized model
            assert memory_increase_gb < 8.0, f"Excessive memory usage: {memory_increase_gb:.1f}GB"
            
            return memory_increase_gb
            
        except Exception as e:
            logger.error(f"[ERROR] Memory test failed: {e}")
            return None
    
    async def test_response_time_optimization(self):
        """Test response time optimization for local LLM."""
        logger.info("[TEST] Testing response time optimization...")
        
        try:
            client = await self.local_llm.get_optimized_client()
            
            # Test simple prompt response time
            start_time = time.time()
            
            response = await client.agenerate_messages([
                {"role": "user", "content": "What is 2+2? Answer briefly."}
            ])
            
            response_time = time.time() - start_time
            
            logger.info(f"[SPEED] Response time: {response_time:.2f}s")
            
            # Should respond within 30 seconds for simple queries
            assert response_time < 30.0, f"Response too slow: {response_time:.2f}s"
            
            # Optimal response time for GTX 1660 Ti should be under 10s
            is_optimal = response_time < 10.0
            
            return {
                'response_time': response_time,
                'is_optimal': is_optimal,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Response time test failed: {e}")
            return None
    
    async def test_concurrent_performance(self):
        """Test performance under concurrent load."""
        logger.info("[TEST] Testing concurrent performance...")
        
        try:
            client = await self.local_llm.get_optimized_client()
            
            # Test 3 concurrent simple requests
            tasks = []
            start_time = time.time()
            
            for i in range(3):
                task = client.agenerate_messages([
                    {"role": "user", "content": f"Count to {i+1}. Answer briefly."}
                ])
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Check for errors
            errors = [r for r in responses if isinstance(r, Exception)]
            successful = len(responses) - len(errors)
            
            logger.info(f"[CONCURRENT] {successful}/3 requests successful in {total_time:.2f}s")
            
            # Should handle at least 2/3 concurrent requests
            assert successful >= 2, f"Too many concurrent failures: {len(errors)}/3"
            
            return {
                'total_time': total_time,
                'successful_requests': successful,
                'failed_requests': len(errors),
                'avg_time_per_request': total_time / 3
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Concurrent performance test failed: {e}")
            return None
    
    async def test_hybrid_orchestrator_performance(self):
        """Test hybrid orchestrator performance optimization."""
        logger.info("[TEST] Testing hybrid orchestrator performance...")
        
        try:
            # Create optimized hybrid config
            hybrid_config = HybridConfig()
            hybrid_config.local_config = self.config
            
            orchestrator = HybridOrchestrator(hybrid_config)
            
            # Test performance monitoring
            monitor = orchestrator.performance_monitor
            
            # Simulate some steps
            monitor.record_step(True, 5.0)   # Fast success
            monitor.record_step(True, 3.0)   # Faster success
            monitor.record_step(False, 15.0) # Slow failure
            monitor.record_step(True, 4.0)   # Recovery success
            
            success_rate = monitor.get_success_rate()
            avg_time = monitor.metrics['avg_step_time']
            
            logger.info(f"[HYBRID] Success rate: {success_rate:.1%}")
            logger.info(f"[HYBRID] Average step time: {avg_time:.1f}s")
            
            # Should maintain good performance
            assert success_rate >= 0.7, f"Success rate too low: {success_rate:.1%}"
            assert avg_time < 10.0, f"Average step time too high: {avg_time:.1f}s"
            
            return {
                'success_rate': success_rate,
                'avg_step_time': avg_time,
                'should_request_help': monitor.should_request_cloud_help()
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Hybrid orchestrator test failed: {e}")
            return None
    
    async def run_all_tests(self):
        """Run all performance optimization tests."""
        logger.info("[START] Running performance optimization test suite...")
        
        results = {}
        
        # Test 1: GPU acceleration
        results['gpu_acceleration'] = await self.test_gpu_acceleration_enabled()
        
        # Test 2: Memory optimization
        results['memory_optimization'] = await self.test_memory_optimization()
        
        # Test 3: Response time
        results['response_time'] = await self.test_response_time_optimization()
        
        # Test 4: Concurrent performance
        results['concurrent_performance'] = await self.test_concurrent_performance()
        
        # Test 5: Hybrid orchestrator
        results['hybrid_performance'] = await self.test_hybrid_orchestrator_performance()
        
        # Summary
        logger.info("[SUMMARY] Performance Test Results:")
        for test_name, result in results.items():
            if result is not None:
                logger.info(f"  ✅ {test_name}: PASSED")
            else:
                logger.info(f"  ❌ {test_name}: FAILED")
        
        return results

async def main():
    """Run performance optimization tests."""
    logging.basicConfig(level=logging.INFO)
    
    test_suite = PerformanceTestSuite()
    results = await test_suite.run_all_tests()
    
    print("\n" + "="*50)
    print("PERFORMANCE OPTIMIZATION TEST RESULTS")
    print("="*50)
    
    for test_name, result in results.items():
        print(f"\n{test_name.upper()}:")
        if result is not None:
            if isinstance(result, dict):
                for key, value in result.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  Result: {result}")
        else:
            print("  Status: FAILED")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())