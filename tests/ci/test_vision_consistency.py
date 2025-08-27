#!/usr/bin/env python3
"""
Vision Consistency Testing Framework
Tests that the vision system produces consistent, reliable outputs

Key Features:
1. Multiple run consistency analysis with scoring
2. Complete JSON schema validation  
3. Cross-tier consistency comparison
4. Variance metrics for element counts and processing times
5. Regression detection capabilities
"""

import asyncio
import json
import pytest
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import tempfile
from PIL import Image

# Import vision components
from enhanced_vision_architecture import EnhancedVisionSystem, ReliableVisionRequest, ReliableVisionTier
from vision_module import VisionState, VisionElement
from multi_tier_vision import MultiTierVisionSystem

# Test configuration
TEST_SCREENSHOTS_DIR = Path(__file__).parent / "test_screenshots"
TEST_SCREENSHOTS_DIR.mkdir(exist_ok=True)

@dataclass
class ConsistencyTestResult:
    """Results from consistency testing"""
    consistency_score: float
    variance_metrics: Dict[str, float]
    schema_violations: List[str]
    performance_metrics: Dict[str, float]
    cross_tier_consistency: Dict[str, float]


class VisionConsistencyTester:
    """Comprehensive vision consistency testing"""
    
    def __init__(self):
        self.vision_system = None
        self.test_images = []
        
    async def setup(self):
        """Setup test environment"""
        self.vision_system = EnhancedVisionSystem()
        await self._create_test_images()
    
    async def _create_test_images(self):
        """Create standardized test images"""
        test_cases = [
            ("simple_button", self._create_simple_button_image),
            ("form_page", self._create_form_page_image),
            ("complex_layout", self._create_complex_layout_image),
            ("ecommerce_page", self._create_ecommerce_image),
            ("minimal_content", self._create_minimal_content_image)
        ]
        
        for name, creator in test_cases:
            image_path = TEST_SCREENSHOTS_DIR / f"{name}.png"
            if not image_path.exists():
                creator(str(image_path))
            self.test_images.append((name, str(image_path)))
    
    def _create_simple_button_image(self, path: str):
        """Create simple button test image"""
        img = Image.new('RGB', (800, 600), color='white')
        # Would use PIL drawing to create a simple button
        # For now, just create a white image
        img.save(path)
    
    def _create_form_page_image(self, path: str):
        """Create form page test image"""
        img = Image.new('RGB', (800, 600), color='#f0f0f0')
        img.save(path)
    
    def _create_complex_layout_image(self, path: str):
        """Create complex layout test image"""
        img = Image.new('RGB', (1200, 800), color='white')
        img.save(path)
    
    def _create_ecommerce_image(self, path: str):
        """Create e-commerce page test image"""
        img = Image.new('RGB', (1000, 800), color='white')
        img.save(path)
    
    def _create_minimal_content_image(self, path: str):
        """Create minimal content test image"""
        img = Image.new('RGB', (400, 300), color='white')
        img.save(path)
    
    async def test_multiple_run_consistency(self, image_path: str, runs: int = 5) -> ConsistencyTestResult:
        """Test consistency across multiple runs of the same input"""
        results = []
        
        request = ReliableVisionRequest(
            page_url="https://test.example.com",
            page_title="Consistency Test Page",
            screenshot_path=image_path,
            required_accuracy=0.8
        )
        
        # Run multiple analyses
        for i in range(runs):
            try:
                start_time = time.time()
                response = await self.vision_system.analyze(request)
                processing_time = time.time() - start_time
                
                results.append({
                    'run': i + 1,
                    'response': response,
                    'processing_time': processing_time,
                    'elements_count': len(response.vision_state.elements),
                    'confidence': response.confidence,
                    'tier_used': response.tier_used.value
                })
                
                # Brief pause between runs
                await asyncio.sleep(0.5)
                
            except Exception as e:
                results.append({
                    'run': i + 1,
                    'error': str(e),
                    'processing_time': 0,
                    'elements_count': 0,
                    'confidence': 0.0
                })
        
        return await self._analyze_consistency_results(results)
    
    async def _analyze_consistency_results(self, results: List[Dict[str, Any]]) -> ConsistencyTestResult:
        """Analyze consistency across multiple results"""
        
        # Filter successful results
        successful_results = [r for r in results if 'error' not in r]
        total_runs = len(results)
        success_rate = len(successful_results) / total_runs if total_runs > 0 else 0
        
        if not successful_results:
            return ConsistencyTestResult(
                consistency_score=0.0,
                variance_metrics={'success_rate': 0.0},
                schema_violations=['All runs failed'],
                performance_metrics={},
                cross_tier_consistency={}
            )
        
        # Calculate variance metrics
        element_counts = [r['elements_count'] for r in successful_results]
        processing_times = [r['processing_time'] for r in successful_results]
        confidences = [r['confidence'] for r in successful_results]
        tiers_used = [r['tier_used'] for r in successful_results]
        
        variance_metrics = {
            'success_rate': success_rate,
            'element_count_variance': statistics.variance(element_counts) if len(element_counts) > 1 else 0.0,
            'processing_time_variance': statistics.variance(processing_times) if len(processing_times) > 1 else 0.0,
            'confidence_variance': statistics.variance(confidences) if len(confidences) > 1 else 0.0,
            'tier_consistency': len(set(tiers_used)) == 1  # True if all runs used same tier
        }
        
        # Calculate consistency score (higher is better)
        consistency_score = (
            success_rate * 0.4 +  # 40% weight on success rate
            (1.0 - min(1.0, variance_metrics['element_count_variance'] / 10.0)) * 0.3 +  # 30% on element consistency
            (1.0 - min(1.0, variance_metrics['confidence_variance'])) * 0.2 +  # 20% on confidence consistency
            (1.0 if variance_metrics['tier_consistency'] else 0.5) * 0.1  # 10% on tier consistency
        )
        
        # Check schema violations
        schema_violations = []
        for result in successful_results:
            violations = await self._check_schema_compliance(result['response'])
            schema_violations.extend(violations)
        
        # Performance metrics
        performance_metrics = {
            'avg_processing_time': statistics.mean(processing_times),
            'max_processing_time': max(processing_times),
            'min_processing_time': min(processing_times),
            'avg_confidence': statistics.mean(confidences),
            'avg_elements_found': statistics.mean(element_counts)
        }
        
        return ConsistencyTestResult(
            consistency_score=consistency_score,
            variance_metrics=variance_metrics,
            schema_violations=list(set(schema_violations)),  # Remove duplicates
            performance_metrics=performance_metrics,
            cross_tier_consistency={}
        )
    
    async def _check_schema_compliance(self, response) -> List[str]:
        """Check if response complies with expected schema"""
        violations = []
        
        try:
            # Check basic response structure
            if not hasattr(response, 'vision_state'):
                violations.append("Missing vision_state")
                return violations
            
            vision_state = response.vision_state
            
            # Check VisionState structure
            if not hasattr(vision_state, 'caption'):
                violations.append("Missing caption")
            elif not isinstance(vision_state.caption, str):
                violations.append("Caption is not a string")
            
            if not hasattr(vision_state, 'elements'):
                violations.append("Missing elements")
            elif not isinstance(vision_state.elements, list):
                violations.append("Elements is not a list")
            else:
                # Check each element
                for i, element in enumerate(vision_state.elements):
                    element_violations = self._check_element_schema(element, i)
                    violations.extend(element_violations)
            
            if not hasattr(vision_state, 'fields'):
                violations.append("Missing fields")
            elif not isinstance(vision_state.fields, list):
                violations.append("Fields is not a list")
            
            if not hasattr(vision_state, 'affordances'):
                violations.append("Missing affordances")
            elif not isinstance(vision_state.affordances, list):
                violations.append("Affordances is not a list")
            
            if not hasattr(vision_state, 'meta'):
                violations.append("Missing meta")
            
        except Exception as e:
            violations.append(f"Schema check error: {e}")
        
        return violations
    
    def _check_element_schema(self, element, index: int) -> List[str]:
        """Check individual element schema compliance"""
        violations = []
        prefix = f"Element[{index}]"
        
        # Check required fields
        required_fields = ['role', 'visible_text', 'attributes', 'selector_hint', 'bbox', 'confidence']
        
        for field in required_fields:
            if not hasattr(element, field):
                violations.append(f"{prefix}: Missing {field}")
        
        # Check field types
        if hasattr(element, 'role') and not isinstance(element.role, str):
            violations.append(f"{prefix}: role is not string")
        
        if hasattr(element, 'visible_text') and not isinstance(element.visible_text, str):
            violations.append(f"{prefix}: visible_text is not string")
        
        if hasattr(element, 'bbox') and not isinstance(element.bbox, list):
            violations.append(f"{prefix}: bbox is not list")
        elif hasattr(element, 'bbox') and len(element.bbox) != 4:
            violations.append(f"{prefix}: bbox does not have 4 coordinates")
        
        if hasattr(element, 'confidence') and not isinstance(element.confidence, (int, float)):
            violations.append(f"{prefix}: confidence is not numeric")
        elif hasattr(element, 'confidence') and not (0 <= element.confidence <= 1):
            violations.append(f"{prefix}: confidence not in range 0-1")
        
        return violations
    
    async def test_cross_tier_consistency(self, image_path: str) -> Dict[str, Any]:
        """Test consistency between different vision tiers"""
        tiers_to_test = [
            ReliableVisionTier.TIER1_DOM_ENHANCED,
            ReliableVisionTier.TIER2_LIGHTWEIGHT,
            ReliableVisionTier.TIER3_CLOUD_RELIABLE
        ]
        
        results = {}
        
        for tier in tiers_to_test:
            request = ReliableVisionRequest(
                page_url="https://test.example.com",
                page_title="Cross-tier Test Page",
                screenshot_path=image_path,
                force_tier=tier
            )
            
            try:
                response = await self.vision_system.analyze(request)
                results[tier.value] = {
                    'elements_count': len(response.vision_state.elements),
                    'confidence': response.confidence,
                    'processing_time': response.analysis_time,
                    'elements': [
                        {'role': e.role, 'text': e.visible_text, 'bbox': e.bbox} 
                        for e in response.vision_state.elements
                    ]
                }
            except Exception as e:
                results[tier.value] = {'error': str(e)}
        
        # Analyze cross-tier consistency
        successful_tiers = {k: v for k, v in results.items() if 'error' not in v}
        
        consistency_metrics = {}
        if len(successful_tiers) >= 2:
            tier_names = list(successful_tiers.keys())
            
            # Compare element counts
            element_counts = [v['elements_count'] for v in successful_tiers.values()]
            consistency_metrics['element_count_similarity'] = 1.0 - (statistics.variance(element_counts) / max(1, statistics.mean(element_counts)))
            
            # Compare confidence scores
            confidences = [v['confidence'] for v in successful_tiers.values()]
            consistency_metrics['confidence_similarity'] = 1.0 - statistics.variance(confidences)
            
            # Overall cross-tier consistency
            consistency_metrics['overall_consistency'] = (
                consistency_metrics['element_count_similarity'] * 0.6 +
                consistency_metrics['confidence_similarity'] * 0.4
            )
        
        return {
            'tier_results': results,
            'consistency_metrics': consistency_metrics
        }


# Pytest test cases
@pytest.mark.asyncio
class TestVisionConsistency:
    """Pytest test class for vision consistency"""
    
    @pytest.fixture(scope="class")
    async def vision_tester(self):
        """Setup vision consistency tester"""
        tester = VisionConsistencyTester()
        await tester.setup()
        return tester
    
    @pytest.mark.asyncio
    async def test_simple_button_consistency(self, vision_tester):
        """Test consistency on simple button image"""
        simple_button_path = None
        for name, path in vision_tester.test_images:
            if name == "simple_button":
                simple_button_path = path
                break
        
        assert simple_button_path is not None, "Simple button test image not found"
        
        result = await vision_tester.test_multiple_run_consistency(simple_button_path, runs=3)
        
        # Assertions
        assert result.consistency_score >= 0.7, f"Consistency score too low: {result.consistency_score}"
        assert result.variance_metrics['success_rate'] >= 0.8, f"Success rate too low: {result.variance_metrics['success_rate']}"
        assert len(result.schema_violations) == 0, f"Schema violations found: {result.schema_violations}"
        assert result.performance_metrics['avg_processing_time'] < 30.0, f"Processing time too slow: {result.performance_metrics['avg_processing_time']}s"
    
    @pytest.mark.asyncio
    async def test_complex_layout_consistency(self, vision_tester):
        """Test consistency on complex layout image"""
        complex_layout_path = None
        for name, path in vision_tester.test_images:
            if name == "complex_layout":
                complex_layout_path = path
                break
        
        assert complex_layout_path is not None, "Complex layout test image not found"
        
        result = await vision_tester.test_multiple_run_consistency(complex_layout_path, runs=3)
        
        # More lenient requirements for complex layouts
        assert result.consistency_score >= 0.6, f"Consistency score too low: {result.consistency_score}"
        assert result.variance_metrics['success_rate'] >= 0.7, f"Success rate too low: {result.variance_metrics['success_rate']}"
        assert len(result.schema_violations) == 0, f"Schema violations found: {result.schema_violations}"
    
    @pytest.mark.asyncio
    async def test_cross_tier_consistency(self, vision_tester):
        """Test consistency across different vision tiers"""
        simple_button_path = None
        for name, path in vision_tester.test_images:
            if name == "simple_button":
                simple_button_path = path
                break
        
        assert simple_button_path is not None, "Simple button test image not found"
        
        result = await vision_tester.test_cross_tier_consistency(simple_button_path)
        
        # Check that multiple tiers succeeded
        successful_tiers = {k: v for k, v in result['tier_results'].items() if 'error' not in v}
        assert len(successful_tiers) >= 2, f"Not enough tiers succeeded: {list(successful_tiers.keys())}"
        
        # Check consistency metrics
        if 'consistency_metrics' in result and result['consistency_metrics']:
            assert result['consistency_metrics']['overall_consistency'] >= 0.5, \
                f"Cross-tier consistency too low: {result['consistency_metrics']['overall_consistency']}"
    
    @pytest.mark.asyncio
    async def test_schema_compliance_all_images(self, vision_tester):
        """Test schema compliance across all test images"""
        schema_violations_by_image = {}
        
        for name, image_path in vision_tester.test_images:
            result = await vision_tester.test_multiple_run_consistency(image_path, runs=2)
            if result.schema_violations:
                schema_violations_by_image[name] = result.schema_violations
        
        # Assert no schema violations across any images
        assert len(schema_violations_by_image) == 0, \
            f"Schema violations found: {schema_violations_by_image}"
    
    @pytest.mark.asyncio
    async def test_performance_consistency(self, vision_tester):
        """Test that performance is consistent across runs"""
        form_page_path = None
        for name, path in vision_tester.test_images:
            if name == "form_page":
                form_page_path = path
                break
        
        assert form_page_path is not None, "Form page test image not found"
        
        result = await vision_tester.test_multiple_run_consistency(form_page_path, runs=4)
        
        # Check performance consistency
        assert result.performance_metrics['max_processing_time'] / result.performance_metrics['min_processing_time'] < 3.0, \
            f"Processing time too variable: {result.performance_metrics['max_processing_time']:.2f}s max vs {result.performance_metrics['min_processing_time']:.2f}s min"
        
        assert result.variance_metrics['processing_time_variance'] < 25.0, \
            f"Processing time variance too high: {result.variance_metrics['processing_time_variance']}"


# Standalone test runner
async def run_consistency_tests():
    """Run consistency tests standalone"""
    print("Starting vision consistency tests...")
    
    tester = VisionConsistencyTester()
    await tester.setup()
    
    test_results = {}
    
    for name, image_path in tester.test_images:
        print(f"\nTesting consistency for {name}...")
        
        try:
            result = await tester.test_multiple_run_consistency(image_path, runs=3)
            test_results[name] = {
                'consistency_score': result.consistency_score,
                'success_rate': result.variance_metrics['success_rate'],
                'schema_violations': len(result.schema_violations),
                'avg_processing_time': result.performance_metrics.get('avg_processing_time', 0),
                'passed': (result.consistency_score >= 0.6 and 
                          result.variance_metrics['success_rate'] >= 0.7 and
                          len(result.schema_violations) == 0)
            }
            
            print(f"  Consistency Score: {result.consistency_score:.3f}")
            print(f"  Success Rate: {result.variance_metrics['success_rate']:.1%}")
            print(f"  Schema Violations: {len(result.schema_violations)}")
            print(f"  Avg Processing Time: {result.performance_metrics.get('avg_processing_time', 0):.2f}s")
            
        except Exception as e:
            test_results[name] = {'error': str(e), 'passed': False}
            print(f"  ERROR: {e}")
    
    # Summary
    passed_tests = sum(1 for r in test_results.values() if r.get('passed', False))
    total_tests = len(test_results)
    
    print(f"\n{'='*60}")
    print(f"CONSISTENCY TEST SUMMARY")
    print(f"Passed: {passed_tests}/{total_tests} tests")
    print(f"Success Rate: {passed_tests/total_tests:.1%}")
    
    if passed_tests < total_tests:
        print("\nFAILED TESTS:")
        for name, result in test_results.items():
            if not result.get('passed', False):
                print(f"  {name}: {result}")
    
    return test_results


if __name__ == "__main__":
    asyncio.run(run_consistency_tests())