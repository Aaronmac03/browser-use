#!/usr/bin/env python3
"""
Multi-Tier Vision System - Intelligent routing between different vision analysis methods
Implements the tiered approach outlined in the improvement plan
"""

import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field
from playwright.async_api import Page

# Import existing components
from vision_module import VisionAnalyzer, VisionState, VisionMeta
from enhanced_dom_analyzer import EnhancedDOMAnalyzer


class VisionTier(Enum):
    """Vision analysis tiers"""
    TIER1_DOM = "tier1_dom"           # Ultra-fast DOM analysis (< 100ms)
    TIER2_LIGHTWEIGHT = "tier2_light" # Lightweight vision models (< 2s)
    TIER3_ADVANCED = "tier3_advanced" # Advanced vision models (< 10s)
    FALLBACK = "fallback"             # Emergency fallback


class AnalysisComplexity(Enum):
    """Page complexity levels"""
    SIMPLE = "simple"       # Basic pages with clear structure
    MEDIUM = "medium"       # Moderate complexity
    COMPLEX = "complex"     # High complexity requiring advanced analysis


class VisionRequest(BaseModel):
    """Request for vision analysis"""
    page_url: str = Field(description="Current page URL")
    page_title: str = Field(description="Page title")
    screenshot_path: Optional[str] = Field(description="Path to screenshot", default=None)
    required_accuracy: float = Field(description="Required accuracy (0.0-1.0)", default=0.8)
    max_response_time: float = Field(description="Maximum acceptable response time in seconds", default=5.0)
    force_tier: Optional[VisionTier] = Field(description="Force specific tier", default=None)


class VisionResponse(BaseModel):
    """Response from vision analysis"""
    vision_state: VisionState
    tier_used: VisionTier
    analysis_time: float
    confidence: float
    fallback_reason: Optional[str] = Field(default=None)


class ModelPerformanceTracker:
    """Track performance of different vision models"""
    
    def __init__(self):
        self.stats = {
            VisionTier.TIER1_DOM: {
                'total_calls': 0,
                'successful_calls': 0,
                'avg_response_time': 0.0,
                'avg_confidence': 0.0,
                'last_success_time': None,
                'consecutive_failures': 0
            },
            VisionTier.TIER2_LIGHTWEIGHT: {
                'total_calls': 0,
                'successful_calls': 0,
                'avg_response_time': 0.0,
                'avg_confidence': 0.0,
                'last_success_time': None,
                'consecutive_failures': 0
            },
            VisionTier.TIER3_ADVANCED: {
                'total_calls': 0,
                'successful_calls': 0,
                'avg_response_time': 0.0,
                'avg_confidence': 0.0,
                'last_success_time': None,
                'consecutive_failures': 0
            }
        }
    
    def record_success(self, tier: VisionTier, response_time: float, confidence: float):
        """Record successful analysis"""
        if tier not in self.stats:
            return
            
        stats = self.stats[tier]
        stats['total_calls'] += 1
        stats['successful_calls'] += 1
        stats['consecutive_failures'] = 0
        stats['last_success_time'] = time.time()
        
        # Update rolling averages
        total_successful = stats['successful_calls']
        stats['avg_response_time'] = (
            (stats['avg_response_time'] * (total_successful - 1) + response_time) / total_successful
        )
        stats['avg_confidence'] = (
            (stats['avg_confidence'] * (total_successful - 1) + confidence) / total_successful
        )
    
    def record_failure(self, tier: VisionTier, response_time: float):
        """Record failed analysis"""
        if tier not in self.stats:
            return
            
        stats = self.stats[tier]
        stats['total_calls'] += 1
        stats['consecutive_failures'] += 1
    
    def get_success_rate(self, tier: VisionTier) -> float:
        """Get success rate for a tier"""
        if tier not in self.stats:
            return 0.0
            
        stats = self.stats[tier]
        if stats['total_calls'] == 0:
            return 1.0  # Assume good until proven otherwise
            
        return stats['successful_calls'] / stats['total_calls']
    
    def is_tier_healthy(self, tier: VisionTier) -> bool:
        """Check if a tier is performing well"""
        if tier not in self.stats:
            return False
            
        stats = self.stats[tier]
        
        # Consider unhealthy if:
        # - More than 3 consecutive failures
        # - Success rate below 50% with at least 5 attempts
        if stats['consecutive_failures'] > 3:
            return False
            
        if stats['total_calls'] >= 5 and self.get_success_rate(tier) < 0.5:
            return False
            
        return True
    
    def get_best_tier_for_requirements(self, max_time: float, min_confidence: float) -> Optional[VisionTier]:
        """Get the best tier that meets requirements"""
        
        # Check each tier in order of preference
        tiers_by_preference = [
            VisionTier.TIER1_DOM,
            VisionTier.TIER2_LIGHTWEIGHT,
            VisionTier.TIER3_ADVANCED
        ]
        
        for tier in tiers_by_preference:
            if not self.is_tier_healthy(tier):
                continue
                
            stats = self.stats[tier]
            
            # Check if tier meets time requirements
            if stats['avg_response_time'] > 0 and stats['avg_response_time'] > max_time:
                continue
                
            # Check if tier meets confidence requirements
            if stats['avg_confidence'] > 0 and stats['avg_confidence'] < min_confidence:
                continue
                
            return tier
        
        return None


class ComplexityAnalyzer:
    """Analyze page complexity to determine appropriate vision tier"""
    
    @staticmethod
    async def analyze_page_complexity(page: Page) -> AnalysisComplexity:
        """Analyze page complexity based on DOM structure"""
        try:
            # Count various elements to determine complexity
            complexity_metrics = await page.evaluate("""
                () => {
                    const metrics = {
                        totalElements: document.querySelectorAll('*').length,
                        interactiveElements: document.querySelectorAll('button, a, input, select, textarea, [onclick], [role="button"]').length,
                        formElements: document.querySelectorAll('form, input, select, textarea').length,
                        images: document.querySelectorAll('img').length,
                        iframes: document.querySelectorAll('iframe').length,
                        canvasElements: document.querySelectorAll('canvas').length,
                        svgElements: document.querySelectorAll('svg').length,
                        dynamicContent: document.querySelectorAll('[data-react], [ng-], [v-], .vue-').length,
                        hasOverlays: document.querySelectorAll('.modal, .popup, .overlay, .dropdown-menu').length > 0,
                        hasComplexLayouts: document.querySelectorAll('.grid, .flex, .absolute, .fixed').length > 10
                    };
                    return metrics;
                }
            """)
            
            # Determine complexity based on metrics
            if (complexity_metrics['totalElements'] > 1000 or
                complexity_metrics['interactiveElements'] > 50 or
                complexity_metrics['canvasElements'] > 0 or
                complexity_metrics['iframes'] > 2 or
                complexity_metrics['dynamicContent'] > 10 or
                complexity_metrics['hasOverlays']):
                return AnalysisComplexity.COMPLEX
            
            elif (complexity_metrics['totalElements'] > 200 or
                  complexity_metrics['interactiveElements'] > 10 or
                  complexity_metrics['formElements'] > 5 or
                  complexity_metrics['images'] > 20):
                return AnalysisComplexity.MEDIUM
            
            else:
                return AnalysisComplexity.SIMPLE
                
        except Exception as e:
            print(f"[ComplexityAnalyzer] Error analyzing complexity: {e}")
            return AnalysisComplexity.MEDIUM  # Default to medium on error


class MultiTierVisionSystem:
    """Multi-tier vision system with intelligent routing"""
    
    def __init__(self):
        # Initialize tier analyzers
        self.tier1_analyzer = EnhancedDOMAnalyzer()
        self.tier2_analyzer = None  # Placeholder for lightweight vision model
        self.tier3_analyzer = VisionAnalyzer()  # Current Moondream analyzer
        
        # Performance tracking
        self.performance_tracker = ModelPerformanceTracker()
        self.complexity_analyzer = ComplexityAnalyzer()
        
        # Configuration
        self.config = {
            'tier1_max_time': 0.5,      # 500ms for DOM analysis
            'tier2_max_time': 3.0,      # 3s for lightweight models
            'tier3_max_time': 15.0,     # 15s for advanced models
            'min_confidence_threshold': 0.7,
            'enable_fallback_chain': True,
            'max_fallback_attempts': 2
        }
    
    async def analyze(self, request: VisionRequest, page: Optional[Page] = None) -> VisionResponse:
        """Main analysis method with intelligent tier selection"""
        start_time = time.time()
        
        try:
            # Determine optimal tier
            if request.force_tier:
                selected_tier = request.force_tier
                print(f"[MultiTierVision] Using forced tier: {selected_tier.value}")
            else:
                selected_tier = await self._select_optimal_tier(request, page)
                print(f"[MultiTierVision] Selected tier: {selected_tier.value}")
            
            # Attempt analysis with selected tier
            response = await self._analyze_with_tier(selected_tier, request, page)
            
            # Check if fallback is needed
            if (self.config['enable_fallback_chain'] and 
                response.confidence < request.required_accuracy and
                selected_tier != VisionTier.FALLBACK):
                
                print(f"[MultiTierVision] Confidence {response.confidence:.2f} below threshold {request.required_accuracy:.2f}, attempting fallback")
                fallback_response = await self._attempt_fallback(selected_tier, request, page)
                if fallback_response.confidence > response.confidence:
                    return fallback_response
            
            return response
            
        except Exception as e:
            print(f"[MultiTierVision] Analysis failed: {e}")
            # Return emergency fallback
            return VisionResponse(
                vision_state=VisionState(
                    caption=f"Vision analysis failed: {str(e)[:100]}",
                    meta=VisionMeta(
                        url=request.page_url,
                        title=request.page_title,
                        model_name="emergency_fallback",
                        confidence=0.0,
                        processing_time=time.time() - start_time
                    )
                ),
                tier_used=VisionTier.FALLBACK,
                analysis_time=time.time() - start_time,
                confidence=0.0,
                fallback_reason=str(e)
            )
    
    async def _select_optimal_tier(self, request: VisionRequest, page: Optional[Page]) -> VisionTier:
        """Select the optimal tier based on requirements and performance"""
        
        # Analyze page complexity if page is available
        complexity = AnalysisComplexity.MEDIUM
        if page:
            complexity = await self.complexity_analyzer.analyze_page_complexity(page)
            print(f"[MultiTierVision] Page complexity: {complexity.value}")
        
        # Get best tier based on performance requirements
        best_tier = self.performance_tracker.get_best_tier_for_requirements(
            request.max_response_time,
            request.required_accuracy
        )
        
        if best_tier:
            print(f"[MultiTierVision] Performance-based selection: {best_tier.value}")
            return best_tier
        
        # Fallback to complexity-based selection
        if complexity == AnalysisComplexity.SIMPLE:
            return VisionTier.TIER1_DOM
        elif complexity == AnalysisComplexity.MEDIUM:
            # Choose between Tier 1 and Tier 3 (skip Tier 2 for now)
            if request.max_response_time < 2.0:
                return VisionTier.TIER1_DOM
            else:
                return VisionTier.TIER3_ADVANCED
        else:  # COMPLEX
            return VisionTier.TIER3_ADVANCED
    
    async def _analyze_with_tier(self, tier: VisionTier, request: VisionRequest, page: Optional[Page]) -> VisionResponse:
        """Perform analysis with specific tier"""
        start_time = time.time()
        
        try:
            if tier == VisionTier.TIER1_DOM:
                if not page:
                    raise ValueError("Page object required for DOM analysis")
                vision_state = await self.tier1_analyzer.analyze_page(page, request.page_url, request.page_title)
                
            elif tier == VisionTier.TIER2_LIGHTWEIGHT:
                # Placeholder for lightweight vision model
                raise NotImplementedError("Tier 2 lightweight vision model not yet implemented")
                
            elif tier == VisionTier.TIER3_ADVANCED:
                if not request.screenshot_path:
                    raise ValueError("Screenshot path required for advanced vision analysis")
                vision_state = await self.tier3_analyzer.analyze(request.screenshot_path, request.page_url, request.page_title)
                
            else:
                raise ValueError(f"Unknown tier: {tier}")
            
            analysis_time = time.time() - start_time
            confidence = vision_state.meta.confidence
            
            # Record success
            self.performance_tracker.record_success(tier, analysis_time, confidence)
            
            return VisionResponse(
                vision_state=vision_state,
                tier_used=tier,
                analysis_time=analysis_time,
                confidence=confidence
            )
            
        except Exception as e:
            analysis_time = time.time() - start_time
            self.performance_tracker.record_failure(tier, analysis_time)
            raise e
    
    async def _attempt_fallback(self, failed_tier: VisionTier, request: VisionRequest, page: Optional[Page]) -> VisionResponse:
        """Attempt fallback to other tiers"""
        
        # Define fallback chain
        fallback_chain = []
        
        if failed_tier == VisionTier.TIER1_DOM:
            fallback_chain = [VisionTier.TIER3_ADVANCED]
        elif failed_tier == VisionTier.TIER2_LIGHTWEIGHT:
            fallback_chain = [VisionTier.TIER1_DOM, VisionTier.TIER3_ADVANCED]
        elif failed_tier == VisionTier.TIER3_ADVANCED:
            fallback_chain = [VisionTier.TIER1_DOM]
        
        for fallback_tier in fallback_chain:
            try:
                print(f"[MultiTierVision] Attempting fallback to {fallback_tier.value}")
                response = await self._analyze_with_tier(fallback_tier, request, page)
                response.fallback_reason = f"Fallback from {failed_tier.value}"
                return response
                
            except Exception as e:
                print(f"[MultiTierVision] Fallback to {fallback_tier.value} failed: {e}")
                continue
        
        # If all fallbacks fail, return minimal response
        return VisionResponse(
            vision_state=VisionState(
                caption="All vision analysis methods failed",
                meta=VisionMeta(
                    url=request.page_url,
                    title=request.page_title,
                    model_name="fallback_failed",
                    confidence=0.0,
                    processing_time=0.0
                )
            ),
            tier_used=VisionTier.FALLBACK,
            analysis_time=0.0,
            confidence=0.0,
            fallback_reason="All tiers failed"
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all tiers"""
        summary = {}
        
        for tier in VisionTier:
            if tier == VisionTier.FALLBACK:
                continue
                
            stats = self.performance_tracker.stats.get(tier, {})
            summary[tier.value] = {
                'success_rate': self.performance_tracker.get_success_rate(tier),
                'avg_response_time': stats.get('avg_response_time', 0.0),
                'avg_confidence': stats.get('avg_confidence', 0.0),
                'total_calls': stats.get('total_calls', 0),
                'is_healthy': self.performance_tracker.is_tier_healthy(tier)
            }
        
        return summary
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all tiers"""
        health_status = {}
        
        # Check Tier 1 (DOM Analyzer)
        try:
            # DOM analyzer doesn't need external dependencies
            health_status['tier1_dom'] = {
                'status': 'healthy',
                'message': 'DOM analyzer ready'
            }
        except Exception as e:
            health_status['tier1_dom'] = {
                'status': 'unhealthy',
                'message': str(e)
            }
        
        # Check Tier 2 (Lightweight Vision)
        health_status['tier2_lightweight'] = {
            'status': 'not_implemented',
            'message': 'Lightweight vision model not yet implemented'
        }
        
        # Check Tier 3 (Advanced Vision)
        try:
            is_available = await self.tier3_analyzer.check_ollama_availability()
            if is_available:
                health_status['tier3_advanced'] = {
                    'status': 'healthy',
                    'message': 'Ollama service available'
                }
            else:
                health_status['tier3_advanced'] = {
                    'status': 'unhealthy',
                    'message': 'Ollama service not available'
                }
        except Exception as e:
            health_status['tier3_advanced'] = {
                'status': 'unhealthy',
                'message': str(e)
            }
        
        return health_status


# Test function
async def test_multi_tier_vision():
    """Test the multi-tier vision system"""
    from playwright.async_api import async_playwright
    import tempfile
    from PIL import Image
    
    vision_system = MultiTierVisionSystem()
    
    # Create a test image
    img = Image.new('RGB', (800, 600), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        img.save(temp_file.name)
        screenshot_path = temp_file.name
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")
        
        # Test different scenarios
        test_cases = [
            {
                'name': 'Fast DOM Analysis',
                'request': VisionRequest(
                    page_url=page.url,
                    page_title=await page.title(),
                    max_response_time=1.0,
                    required_accuracy=0.7,
                    force_tier=VisionTier.TIER1_DOM
                )
            },
            {
                'name': 'Advanced Vision Analysis',
                'request': VisionRequest(
                    page_url=page.url,
                    page_title=await page.title(),
                    screenshot_path=screenshot_path,
                    max_response_time=10.0,
                    required_accuracy=0.8,
                    force_tier=VisionTier.TIER3_ADVANCED
                )
            },
            {
                'name': 'Automatic Tier Selection',
                'request': VisionRequest(
                    page_url=page.url,
                    page_title=await page.title(),
                    screenshot_path=screenshot_path,
                    max_response_time=5.0,
                    required_accuracy=0.8
                )
            }
        ]
        
        for test_case in test_cases:
            print(f"\n=== {test_case['name']} ===")
            try:
                response = await vision_system.analyze(test_case['request'], page)
                print(f"Tier used: {response.tier_used.value}")
                print(f"Analysis time: {response.analysis_time:.3f}s")
                print(f"Confidence: {response.confidence:.2f}")
                print(f"Elements found: {len(response.vision_state.elements)}")
                if response.fallback_reason:
                    print(f"Fallback reason: {response.fallback_reason}")
            except Exception as e:
                print(f"Test failed: {e}")
        
        # Print performance summary
        print("\n=== Performance Summary ===")
        summary = vision_system.get_performance_summary()
        for tier, stats in summary.items():
            print(f"{tier}: {stats}")
        
        # Health check
        print("\n=== Health Check ===")
        health = await vision_system.health_check()
        for tier, status in health.items():
            print(f"{tier}: {status['status']} - {status['message']}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_multi_tier_vision())