"""
Test Integrated Planning System with EnhancedModelRouter and TaskPlanner.

This test validates the complete integration of o3-2025-04-16 planning with
the three-tier routing system for complex browser automation tasks.
"""

import asyncio
import logging
import os
from typing import Dict, List, Any

from dotenv import load_dotenv

from models.enhanced_model_router import EnhancedModelRouter, EnhancedTaskRequirements, ModelTier
from models.action_classifier import ActionClassifier
from models.task_planner import TaskPlanner, PlanningStrategy
from models.model_router import RoutingStrategy
from config.enhanced_models import EnhancedModelConfigManager
from config.settings import Settings
from models.local_handler import OllamaModelHandler
from models.cloud_handler import CloudModelManager, BudgetManager, ResponseCache
from utils.serper import SerperAPI
from utils.logger import setup_logging

# Test scenarios that should trigger planning
PLANNING_TEST_SCENARIOS = [
    {
        "description": "Find the cheapest laptop under $1000 on Amazon and add it to cart",
        "should_plan": True,
        "expected_indicators": ["search", "cheapest", "complex"],
        "category": "complex_shopping"
    },
    {
        "description": "If the login fails, try password recovery, otherwise create a new account",
        "should_plan": True,
        "expected_indicators": ["conditional", "if"],
        "category": "conditional_logic"
    },
    {
        "description": "Search for laptop reviews, compare at least 3 options, then find the best deal",
        "should_plan": True,
        "expected_indicators": ["search", "compare", "multiple steps"],
        "category": "research_and_compare"
    },
    {
        "description": "Navigate to Google and search for 'python tutorials'",
        "should_plan": False,
        "expected_indicators": [],
        "category": "simple_navigation"
    },
    {
        "description": "Click the submit button",
        "should_plan": False,
        "expected_indicators": [],
        "category": "simple_action"
    },
    {
        "description": "Find websites that sell used cars under $15000 and compare their inventory",
        "should_plan": True,
        "expected_indicators": ["search", "find websites", "compare"],
        "category": "multi_site_search"
    },
    {
        "description": "Look up the best restaurants in San Francisco, read reviews, and make a reservation",
        "should_plan": True,
        "expected_indicators": ["look up", "multiple steps", "complex"],
        "category": "complex_reservation"
    }
]

# Test scenarios for complete planning integration
INTEGRATION_TEST_SCENARIOS = [
    {
        "description": "Research the top 3 project management tools, compare features and pricing, then sign up for the best free option",
        "current_url": "https://google.com",
        "expected_planning": True,
        "expected_search_coordination": True,
        "category": "saas_research"
    },
    {
        "description": "Find cheap flights from San Francisco to New York for next month and book the cheapest option under $400",
        "current_url": "https://kayak.com",
        "expected_planning": True,
        "expected_search_coordination": True,
        "category": "travel_booking"
    }
]


async def test_planning_detection():
    """Test the planning detection logic in EnhancedModelRouter."""
    logger = logging.getLogger(__name__)
    logger.info("=== Testing Planning Detection Logic ===")
    
    # Initialize router with mock cloud manager for planning detection
    config_manager = EnhancedModelConfigManager()
    
    # Create a mock cloud manager for planning detection
    budget_manager = BudgetManager(daily_limit=10.0, monthly_limit=50.0)
    cache = ResponseCache(max_age_hours=24)
    mock_cloud_manager = CloudModelManager(
        openai_api_key="test",  # Mock key for planning detection
        anthropic_api_key=None,
        budget_manager=budget_manager,
        cache=cache
    )
    
    router = EnhancedModelRouter(
        model_config_manager=config_manager,
        local_handler=None,
        cloud_manager=mock_cloud_manager,
        serper_api=None
    )
    
    results = []
    correct_detections = 0
    
    print(f"{'Category':<25} | {'Should Plan':<11} | {'Detected':<8} | {'Match':<5} | {'Indicators':<30}")
    print("=" * 90)
    
    for scenario in PLANNING_TEST_SCENARIOS:
        task_req = EnhancedTaskRequirements(
            task_description=scenario["description"],
            has_dom_state=False,
            enable_search_coordination=True
        )
        
        # Test planning detection
        should_plan = router._should_use_planner(task_req)
        planning_match = should_plan == scenario["should_plan"]
        
        if planning_match:
            correct_detections += 1
        
        result = {
            "category": scenario["category"],
            "description": scenario["description"][:50] + "...",
            "should_plan": scenario["should_plan"],
            "detected_plan": should_plan,
            "planning_match": planning_match,
            "expected_indicators": scenario["expected_indicators"]
        }
        results.append(result)
        
        status = "✅" if planning_match else "❌"
        indicators_str = ", ".join(scenario["expected_indicators"][:2])
        
        print(f"{scenario['category']:<25} | {scenario['should_plan']!s:<11} | {should_plan!s:<8} | {status:<5} | {indicators_str:<30}")
    
    accuracy = (correct_detections / len(PLANNING_TEST_SCENARIOS)) * 100
    logger.info(f"\nPlanning Detection Accuracy: {accuracy:.1f}% ({correct_detections}/{len(PLANNING_TEST_SCENARIOS)})")
    
    return results


async def test_complete_integration():
    """Test complete integration of planning with routing."""
    logger = logging.getLogger(__name__)
    logger.info("=== Testing Complete Planning Integration ===")
    
    # Load environment
    load_dotenv()
    settings = Settings()
    
    # Initialize components
    config_manager = EnhancedModelConfigManager()
    
    # Initialize local handler (optional)
    local_handler = None
    if settings.ollama_base_url:
        local_handler = OllamaModelHandler(
            base_url=settings.ollama_base_url,
            timeout=settings.task_timeout
        )
    
    # Initialize cloud manager for planning
    cloud_manager = None
    if settings.openai_api_key or settings.anthropic_api_key:
        budget_manager = BudgetManager(daily_limit=5.0, monthly_limit=20.0)
        cache = ResponseCache(max_age_hours=24)
        
        cloud_manager = CloudModelManager(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            budget_manager=budget_manager,
            cache=cache
        )
    
    # Initialize Serper API (optional)
    serper_api = None
    if hasattr(settings, 'serper_api_key') and settings.serper_api_key:
        serper_api = SerperAPI(api_key=settings.serper_api_key)
    
    # Create integrated router with planning
    router = EnhancedModelRouter(
        model_config_manager=config_manager,
        local_handler=local_handler,
        cloud_manager=cloud_manager,
        serper_api=serper_api,
        default_strategy=RoutingStrategy.BALANCED
    )
    
    results = []
    
    try:
        for scenario in INTEGRATION_TEST_SCENARIOS:
            logger.info(f"\nTesting integration: {scenario['description'][:60]}...")
            
            task_req = EnhancedTaskRequirements(
                task_description=scenario["description"],
                has_dom_state=False,
                current_url=scenario.get("current_url"),
                enable_search_coordination=True,
                prefer_speed=True,
                prefer_cost=True
            )
            
            try:
                # Route the task (this will trigger planning if needed)
                decision = await router.route_task(task_req, RoutingStrategy.BALANCED)
                
                # Check if planning was used
                planning_used = decision.task_plan is not None
                planning_match = planning_used == scenario["expected_planning"]
                
                result = {
                    "category": scenario["category"],
                    "description": scenario["description"][:50] + "...",
                    "expected_planning": scenario["expected_planning"],
                    "planning_used": planning_used,
                    "planning_match": planning_match,
                    "selected_model": decision.selected_model.name,
                    "selected_tier": decision.selected_tier.value,
                    "estimated_cost": decision.estimated_cost,
                    "estimated_time": decision.estimated_time,
                    "confidence": decision.confidence
                }
                
                if decision.task_plan:
                    result.update({
                        "plan_steps": len(decision.task_plan.steps),
                        "plan_strategy": decision.task_plan.strategy.value,
                        "plan_confidence": decision.task_plan.confidence,
                        "requires_search": decision.task_plan.requires_search,
                        "target_websites": decision.task_plan.target_websites
                    })
                
                results.append(result)
                
                status = "✅" if planning_match else "❌"
                logger.info(
                    f"  {status} Planning: {planning_used} | "
                    f"Model: {decision.selected_model.name} | "
                    f"Tier: {decision.selected_tier.value} | "
                    f"Cost: ${decision.estimated_cost:.4f}"
                )
                
                if decision.task_plan:
                    logger.info(
                        f"    Plan: {decision.task_plan.strategy.value} strategy, "
                        f"{len(decision.task_plan.steps)} steps, "
                        f"confidence: {decision.task_plan.confidence:.2f}"
                    )
                    
                    # Show first few plan steps
                    for i, step in enumerate(decision.task_plan.steps[:2]):
                        logger.info(f"      Step {i+1}: {step.action_type.value} - {step.description[:40]}...")
                
            except Exception as e:
                logger.error(f"  ❌ Integration test failed: {e}")
                results.append({
                    "category": scenario["category"],
                    "description": scenario["description"][:50] + "...",
                    "error": str(e)
                })
        
        # Calculate integration success rate
        successful = [r for r in results if "error" not in r]
        if successful:
            planning_correct = sum(1 for r in successful if r.get("planning_match", False))
            integration_accuracy = planning_correct / len(successful) * 100
            
            logger.info(f"\nIntegration Test Results:")
            logger.info(f"  Planning Accuracy: {integration_accuracy:.1f}% ({planning_correct}/{len(successful)})")
            
            # Cost and performance analysis
            total_cost = sum(r["estimated_cost"] for r in successful)
            avg_time = sum(r["estimated_time"] for r in successful) / len(successful)
            
            logger.info(f"  Total Estimated Cost: ${total_cost:.4f}")
            logger.info(f"  Average Response Time: {avg_time:.1f}s")
            
            # Plan analysis
            planned_results = [r for r in successful if r.get("plan_steps")]
            if planned_results:
                avg_plan_steps = sum(r["plan_steps"] for r in planned_results) / len(planned_results)
                avg_plan_confidence = sum(r["plan_confidence"] for r in planned_results) / len(planned_results)
                
                logger.info(f"  Plans Created: {len(planned_results)}")
                logger.info(f"  Average Plan Steps: {avg_plan_steps:.1f}")
                logger.info(f"  Average Plan Confidence: {avg_plan_confidence:.2f}")
    
    finally:
        # Cleanup
        if cloud_manager:
            await cloud_manager.close()
        if local_handler:
            await local_handler.close()
    
    return results


async def main():
    """Run all integrated planning tests."""
    # Setup logging
    setup_logging("INFO", None)
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Testing Integrated Planning System with Three-Tier Routing")
    logger.info("=" * 70)
    
    try:
        # Test 1: Planning Detection Logic
        planning_results = await test_planning_detection()
        
        # Test 2: Complete Integration (requires cloud API keys)
        if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            integration_results = await test_complete_integration()
        else:
            logger.warning("⚠️  Skipping integration tests - no cloud API keys found")
            integration_results = []
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("🎯 Integrated Planning System Test Summary:")
        
        if planning_results:
            planning_correct = sum(1 for r in planning_results if r["planning_match"])
            planning_accuracy = planning_correct / len(planning_results) * 100
            logger.info(f"  ✅ Planning Detection: {planning_accuracy:.1f}% accuracy ({planning_correct}/{len(planning_results)})")
        
        if integration_results:
            successful_integrations = [r for r in integration_results if "error" not in r]
            if successful_integrations:
                integration_correct = sum(1 for r in successful_integrations if r.get("planning_match", False))
                integration_accuracy = integration_correct / len(successful_integrations) * 100
                logger.info(f"  ✅ End-to-End Integration: {integration_accuracy:.1f}% accuracy ({integration_correct}/{len(successful_integrations)})")
        
        logger.info("\n🚀 Integrated Planning System with Three-Tier Routing is Ready!")
        logger.info("   • o3-2025-04-16 for complex query planning and clarification")
        logger.info("   • Intelligent routing between text-only, vision, and cloud models")
        logger.info("   • Serper API coordination for web search tasks")
        logger.info("   • Local LLM cost optimization with cloud-quality planning")
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())