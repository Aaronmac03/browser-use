#!/usr/bin/env python3
"""
Simple validation script that can run without external dependencies.
"""

import os
import json
from pathlib import Path

def validate_performance_optimization():
    """Validate that performance optimizations are in place."""
    results = {}
    
    # Test 1: Server configuration
    server_file = Path("e:/ai/start-llama-server.bat")
    if server_file.exists():
        content = server_file.read_text()
        gpu_layers = "--n-gpu-layers 35" in content
        threads = "--threads 6" in content
        batch_size = "--batch-size 512" in content
        
        results['server_config'] = {
            'status': 'PASS' if all([gpu_layers, threads, batch_size]) else 'FAIL',
            'gpu_layers': gpu_layers,
            'threads': threads,
            'batch_size': batch_size
        }
    else:
        results['server_config'] = {'status': 'FAIL', 'reason': 'File not found'}
    
    # Test 2: Configuration files
    config_files = [
        "e:/ai/browser-use/enhanced_local_llm.py",
        "e:/ai/browser-use/hardware_optimization.py",
        "e:/ai/browser-use/hybrid_orchestrator.py",
        "e:/ai/browser-use/performance_optimizer.py"
    ]
    
    files_exist = [Path(f).exists() for f in config_files]
    results['config_files'] = {
        'status': 'PASS' if all(files_exist) else 'FAIL',
        'found': sum(files_exist),
        'total': len(config_files)
    }
    
    # Test 3: LLM configuration
    llm_file = Path("e:/ai/browser-use/enhanced_local_llm.py")
    if llm_file.exists():
        content = llm_file.read_text()
        timeout_opt = "step_timeout: int = 45" in content
        gpu_accel = "enable_gpu_acceleration: bool = True" in content
        hardware_profile = 'hardware_profile: str = "gtx_1660_ti"' in content
        
        results['llm_config'] = {
            'status': 'PASS' if all([timeout_opt, gpu_accel, hardware_profile]) else 'FAIL',
            'timeout_optimization': timeout_opt,
            'gpu_acceleration': gpu_accel,
            'hardware_profile': hardware_profile
        }
    else:
        results['llm_config'] = {'status': 'FAIL', 'reason': 'File not found'}
    
    # Test 4: Hybrid orchestrator
    hybrid_file = Path("e:/ai/browser-use/hybrid_orchestrator.py")
    if hybrid_file.exists():
        content = hybrid_file.read_text()
        local_threshold = "local_first_threshold: float = 0.9" in content
        
        results['hybrid_orchestrator'] = {
            'status': 'PASS' if local_threshold else 'FAIL',
            'local_first_threshold': local_threshold
        }
    else:
        results['hybrid_orchestrator'] = {'status': 'FAIL', 'reason': 'File not found'}
    
    # Overall assessment
    passed_tests = sum(1 for r in results.values() if r.get('status') == 'PASS')
    total_tests = len(results)
    
    results['overall'] = {
        'status': 'PASS' if passed_tests >= 3 else 'FAIL',
        'passed': passed_tests,
        'total': total_tests,
        'success_rate': passed_tests / total_tests
    }
    
    return results

def main():
    print("="*60)
    print("BROWSER-USE PERFORMANCE VALIDATION")
    print("GTX 1660 Ti + i7-9750H + 16GB RAM")
    print("="*60)
    
    results = validate_performance_optimization()
    
    for test_name, result in results.items():
        if test_name == 'overall':
            continue
        
        status = result.get('status', 'UNKNOWN')
        print(f"\n{test_name.upper().replace('_', ' ')}: {status}")
        
        # Show details
        for key, value in result.items():
            if key != 'status' and key != 'reason':
                symbol = "✅" if value else "❌"
                print(f"  {symbol} {key}: {value}")
        
        if 'reason' in result:
            print(f"  Reason: {result['reason']}")
    
    # Overall summary
    overall = results['overall']
    print(f"\n{'='*60}")
    print(f"OVERALL: {overall['status']}")
    print(f"Tests Passed: {overall['passed']}/{overall['total']}")
    print(f"Success Rate: {overall['success_rate']:.1%}")
    
    # Save results
    results_file = Path("e:/ai/browser-use/validation_results.json")
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_file}")
    
    return overall['status'] == 'PASS'

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)