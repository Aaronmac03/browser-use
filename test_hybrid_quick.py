#!/usr/bin/env python3
"""
Quick Hybrid Orchestrator Test
Tests the cloud planning + local execution workflow without full browser automation.
"""

import asyncio
import os
from hybrid_orchestrator import HybridOrchestrator, HybridConfig
from enhanced_local_llm import LocalLLMConfig
from cloud_planner import CloudPlannerConfig

async def test_hybrid_planning():
    """Test hybrid orchestrator planning phase only."""
    
    print("[TEST] Hybrid Orchestrator - Planning Phase")
    print("=" * 50)
    
    # Configure for minimal cloud usage
    config = HybridConfig(
        local_config=LocalLLMConfig(
            base_url="http://localhost:8080",
            model="qwen2.5-7b-instruct-q4_k_m",
            temperature=0.1,
            timeout=30
        ),
        cloud_config=CloudPlannerConfig(
            model="gpt-4o-mini",  # Use cheaper model for testing
            max_planning_calls=2,
            temperature=0.1
        ),
        max_recovery_attempts=1,
        local_first_threshold=0.9  # 90% local processing target
    )
    
    # Initialize orchestrator
    orchestrator = HybridOrchestrator(config)
    
    # Test planning phase
    try:
        print("\n[PHASE 1] Cloud Strategic Planning...")
        task = "Navigate to example.com and extract the main heading text"
        
        plan = await orchestrator.cloud_planner.plan_task(task)
        
        print(f"[SUCCESS] Plan created with {plan.total_steps} steps:")
        for step in plan.steps:
            print(f"  {step.step_number}. {step.action}: {step.description}")
        
        # Test local LLM initialization
        print("\n[PHASE 2] Local LLM Initialization...")
        local_client = await orchestrator.local_llm.get_optimized_client()
        print("[SUCCESS] Local LLM client initialized")
        
        # Get usage stats
        cloud_usage = orchestrator.cloud_planner.get_usage_stats()
        local_ratio = 1.0 - (cloud_usage['planning_calls_used'] / max(cloud_usage['max_planning_calls'], 1))
        
        print(f"\n[METRICS] Cloud API Usage: {cloud_usage['planning_calls_used']}/{cloud_usage['max_planning_calls']}")
        print(f"[METRICS] Local Processing Ratio: {local_ratio:.1%}")
        print(f"[METRICS] Phase 3B Target (90%+ local): {'MET' if local_ratio >= 0.9 else 'MISSED'}")
        
        # Grade the test
        if plan.total_steps > 0 and local_client and local_ratio >= 0.8:
            grade = "A"
            success = True
        elif plan.total_steps > 0 and local_client:
            grade = "B" 
            success = True
        else:
            grade = "F"
            success = False
            
        print(f"\n[RESULT] Hybrid Planning Test: {'PASS' if success else 'FAIL'}")
        print(f"[GRADE] {grade}")
        
        return success, grade, local_ratio
        
    except Exception as e:
        print(f"[ERROR] Hybrid test failed: {e}")
        import traceback
        traceback.print_exc()
        return False, "F", 0.0

if __name__ == "__main__":
    success, grade, ratio = asyncio.run(test_hybrid_planning())
    print(f"\nFINAL RESULT: {'SUCCESS' if success else 'FAILURE'}")
    print(f"GRADE: {grade}")
    print(f"LOCAL PROCESSING: {ratio:.1%}")