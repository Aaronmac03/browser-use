#!/usr/bin/env python3
"""
Simple performance validation script for GTX 1660 Ti optimizations.
Tests that the hardware optimization configurations are working correctly.
"""

import asyncio
import logging
import time
import json
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceValidator:
    """Validate performance optimizations for GTX 1660 Ti."""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def test_server_config_optimization(self):
        """Test that server configuration is optimized for GTX 1660 Ti."""
        logger.info("[TEST] Validating server configuration...")
        
        server_script = Path("e:/ai/start-llama-server.bat")
        if not server_script.exists():
            self.results['server_config'] = {'status': 'FAIL', 'reason': 'Server script not found'}
            return False
        
        content = server_script.read_text()
        
        # Check for GTX 1660 Ti optimizations
        checks = {
            'gpu_layers': '--n-gpu-layers 35' in content,
            'threads': '--threads 6' in content,
            'batch_size': '--batch-size 512' in content,
            'ubatch_size': '--ubatch-size 128' in content,
            'parallel': '--n-parallel 2' in content,
            'flash_attn': '--flash-attn' in content,
            'mlock': '--mlock' in content,
            'no_mmap': '--no-mmap' in content
        }
        
        passed = sum(checks.values())
        total = len(checks)
        
        self.results['server_config'] = {
            'status': 'PASS' if passed >= 6 else 'PARTIAL',
            'passed': passed,
            'total': total,
            'details': checks
        }
        
        logger.info(f"[SERVER] Configuration check: {passed}/{total} optimizations found")
        return passed >= 6
    
    def test_hardware_detection(self):
        """Test hardware detection and profile selection."""
        logger.info("[TEST] Validating hardware detection...")
        
        try:
            # Import our hardware optimizer
            sys.path.append(str(Path("e:/ai/browser-use")))
            from hardware_optimization import HardwareOptimizer
            
            optimizer = HardwareOptimizer()
            profile = optimizer.detect_hardware()
            
            # Check if profile is reasonable for GTX 1660 Ti
            expected_profile = {
                'gpu_layers': lambda x: 20 <= x <= 40,
                'threads': lambda x: 4 <= x <= 8,
                'batch_size': lambda x: 256 <= x <= 1024,
                'gpu_vram_gb': lambda x: x >= 4.0 or x == 0.0  # 0.0 if no GPU detected
            }
            
            profile_checks = {}
            for key, validator in expected_profile.items():
                value = getattr(profile, key)
                profile_checks[key] = validator(value)
            
            passed = sum(profile_checks.values())
            total = len(profile_checks)
            
            self.results['hardware_detection'] = {
                'status': 'PASS' if passed >= 3 else 'FAIL',
                'profile_name': profile.name,
                'passed': passed,
                'total': total,
                'details': profile_checks,
                'detected_values': {
                    'gpu_layers': profile.gpu_layers,
                    'threads': profile.threads,
                    'batch_size': profile.batch_size,
                    'gpu_vram_gb': profile.gpu_vram_gb
                }
            }
            
            logger.info(f"[HARDWARE] Detection check: {passed}/{total} parameters valid")
            logger.info(f"[HARDWARE] Detected profile: {profile.name}")
            return passed >= 3
            
        except Exception as e:
            self.results['hardware_detection'] = {
                'status': 'FAIL',
                'reason': str(e)
            }
            logger.error(f"[HARDWARE] Detection failed: {e}")
            return False
    
    def test_config_files_exist(self):
        """Test that all required configuration files exist."""
        logger.info("[TEST] Validating configuration files...")
        
        required_files = [
            "e:/ai/browser-use/enhanced_local_llm.py",
            "e:/ai/browser-use/hardware_optimization.py", 
            "e:/ai/browser-use/hybrid_orchestrator.py",
            "e:/ai/browser-use/performance_optimizer.py"
        ]
        
        file_checks = {}
        for file_path in required_files:
            path = Path(file_path)
            file_checks[path.name] = path.exists()
        
        passed = sum(file_checks.values())
        total = len(file_checks)
        
        self.results['config_files'] = {
            'status': 'PASS' if passed == total else 'FAIL',
            'passed': passed,
            'total': total,
            'details': file_checks
        }
        
        logger.info(f"[FILES] Configuration files: {passed}/{total} found")
        return passed == total
    
    def test_llm_config_optimization(self):
        """Test that LLM configuration is optimized."""
        logger.info("[TEST] Validating LLM configuration...")
        
        try:
            sys.path.append(str(Path("e:/ai/browser-use")))
            from enhanced_local_llm import LocalLLMConfig
            
            config = LocalLLMConfig()
            
            # Check optimization settings
            checks = {
                'gpu_acceleration': config.enable_gpu_acceleration,
                'fast_timeout': config.step_timeout <= 60,
                'optimized_tokens': config.max_tokens <= 2048,
                'low_temperature': config.temperature <= 0.2,
                'hardware_profile': config.hardware_profile == "gtx_1660_ti"
            }
            
            passed = sum(checks.values())
            total = len(checks)
            
            self.results['llm_config'] = {
                'status': 'PASS' if passed >= 4 else 'FAIL',
                'passed': passed,
                'total': total,
                'details': checks,
                'config_values': {
                    'step_timeout': config.step_timeout,
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                    'hardware_profile': config.hardware_profile
                }
            }
            
            logger.info(f"[LLM] Configuration check: {passed}/{total} optimizations active")
            return passed >= 4
            
        except Exception as e:
            self.results['llm_config'] = {
                'status': 'FAIL',
                'reason': str(e)
            }
            logger.error(f"[LLM] Configuration test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all performance validation tests."""
        logger.info("[START] Running performance validation tests...")
        
        tests = [
            ('Server Configuration', self.test_server_config_optimization),
            ('Hardware Detection', self.test_hardware_detection),
            ('Configuration Files', self.test_config_files_exist),
            ('LLM Configuration', self.test_llm_config_optimization)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed_tests += 1
                    logger.info(f"[✅] {test_name}: PASSED")
                else:
                    logger.warning(f"[❌] {test_name}: FAILED")
            except Exception as e:
                logger.error(f"[💥] {test_name}: ERROR - {e}")
        
        # Overall results
        overall_status = "PASS" if passed_tests >= 3 else "FAIL"
        self.results['overall'] = {
            'status': overall_status,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'success_rate': passed_tests / total_tests,
            'duration': time.time() - self.start_time
        }
        
        logger.info(f"[SUMMARY] Performance validation: {passed_tests}/{total_tests} tests passed")
        logger.info(f"[SUMMARY] Overall status: {overall_status}")
        
        return overall_status == "PASS"
    
    def save_results(self, filepath="e:/ai/browser-use/validation_results.json"):
        """Save validation results to file."""
        try:
            Path(filepath).write_text(json.dumps(self.results, indent=2))
            logger.info(f"[SAVE] Results saved to {filepath}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to save results: {e}")

def main():
    """Run performance validation."""
    print("="*60)
    print("BROWSER-USE PERFORMANCE VALIDATION")
    print("GTX 1660 Ti + i7-9750H + 16GB RAM")
    print("="*60)
    
    validator = PerformanceValidator()
    success = validator.run_all_tests()
    
    print("\n" + "="*60)
    print("VALIDATION RESULTS")
    print("="*60)
    
    for test_name, result in validator.results.items():
        if test_name == 'overall':
            continue
        
        status = result.get('status', 'UNKNOWN')
        print(f"{test_name.upper()}: {status}")
        
        if 'passed' in result and 'total' in result:
            print(f"  Score: {result['passed']}/{result['total']}")
        
        if 'details' in result:
            for detail, value in result['details'].items():
                symbol = "✅" if value else "❌"
                print(f"  {symbol} {detail}")
        
        print()
    
    # Overall summary
    overall = validator.results.get('overall', {})
    print(f"OVERALL: {overall.get('status', 'UNKNOWN')}")
    print(f"Success Rate: {overall.get('success_rate', 0):.1%}")
    print(f"Duration: {overall.get('duration', 0):.1f}s")
    
    # Save results
    validator.save_results()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)