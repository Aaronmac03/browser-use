#!/usr/bin/env python3
"""
Test script for centralized model configuration system.

This script demonstrates the new single-source-of-truth model configuration
and three-tier routing architecture.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.central_model_config import (
	CENTRAL_MODEL_CONFIG,
	get_planner_model, 
	get_tier_models,
	get_escalation_chain,
	get_primary_model,
	ModelTier,
	validate_configuration
)


def test_centralized_configuration():
	"""Test the centralized model configuration system."""
	print("🧪 Testing Centralized Model Configuration System")
	print("=" * 60)
	print()
	
	# Validate configuration
	print("1️⃣ Validating Configuration")
	try:
		validate_configuration()
		print("   ✅ Configuration validation passed")
	except Exception as e:
		print(f"   ❌ Configuration validation failed: {e}")
		return False
	print()
	
	# Test planner model
	print("2️⃣ Testing Universal Planner")
	planner = get_planner_model()
	print(f"   📋 Planner: {planner.name}")
	print(f"   🏭 Provider: {planner.provider.value}")
	print(f"   🧠 Capabilities: {[c.value for c in planner.capabilities]}")
	print(f"   💰 Cost per 1K tokens: ${planner.specs.cost_per_1k_input}")
	assert planner.name == "o3-2025-04-16", f"Expected o3-2025-04-16, got {planner.name}"
	print("   ✅ Planner configuration correct")
	print()
	
	# Test three-tier architecture
	print("3️⃣ Testing Three-Tier Architecture")
	
	# Tier 1: Text Local
	text_models = get_tier_models(ModelTier.TEXT_LOCAL)
	print(f"   🔤 Tier 1 (Text Local): {len(text_models)} models")
	for model in text_models:
		primary = " (PRIMARY)" if model.is_primary else " (fallback)"
		print(f"      - {model.name}{primary} | {model.specs.memory_gb}GB | {model.specs.tokens_per_second} tok/s")
	
	primary_text = get_primary_model(ModelTier.TEXT_LOCAL)
	assert primary_text.name == "qwen3:8b", f"Expected qwen3:8b as primary text model, got {primary_text.name}"
	print("   ✅ Text tier configuration correct")
	print()
	
	# Tier 2: Vision Local  
	vision_models = get_tier_models(ModelTier.VISION_LOCAL)
	print(f"   👁️ Tier 2 (Vision Local): {len(vision_models)} models")
	for model in vision_models:
		primary = " (PRIMARY)" if model.is_primary else " (fallback)"
		print(f"      - {model.name}{primary} | {model.specs.memory_gb}GB | {model.specs.tokens_per_second} tok/s")
	
	primary_vision = get_primary_model(ModelTier.VISION_LOCAL)
	assert primary_vision.name == "qwen2.5vl:7b", f"Expected qwen2.5vl:7b as primary vision model, got {primary_vision.name}"
	print("   ✅ Vision tier configuration correct")
	print()
	
	# Tier 3: Cloud
	cloud_models = get_tier_models(ModelTier.CLOUD)
	print(f"   ☁️ Tier 3 (Cloud): {len(cloud_models)} models")
	for model in cloud_models:
		primary = " (PRIMARY)" if model.is_primary else " (fallback)"
		cost = f"${model.specs.cost_per_1k_input}" if model.specs.cost_per_1k_input else "N/A"
		print(f"      - {model.name}{primary} | {cost}/1K | {model.specs.context_length} ctx")
	
	primary_cloud = get_primary_model(ModelTier.CLOUD)
	assert primary_cloud.name == "gemini-2.5-flash", f"Expected gemini-2.5-flash as primary cloud model, got {primary_cloud.name}"
	print("   ✅ Cloud tier configuration correct")
	print()
	
	# Test escalation chains
	print("4️⃣ Testing Escalation Chains")
	
	text_chain = get_escalation_chain(requires_vision=False)
	vision_chain = get_escalation_chain(requires_vision=True)
	
	print(f"   🔤 Text-first chain: {' → '.join([t.value for t in text_chain])}")
	print(f"   👁️ Vision-first chain: {' → '.join([t.value for t in vision_chain])}")
	
	expected_text_chain = [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]
	expected_vision_chain = [ModelTier.VISION_LOCAL, ModelTier.CLOUD]
	
	assert text_chain == expected_text_chain, f"Text chain mismatch: {text_chain} vs {expected_text_chain}"
	assert vision_chain == expected_vision_chain, f"Vision chain mismatch: {vision_chain} vs {expected_vision_chain}"
	print("   ✅ Escalation chains correct")
	print()
	
	# Test system compatibility  
	print("5️⃣ Testing System Compatibility")
	compatibility = CENTRAL_MODEL_CONFIG.validate_system_compatibility(16.0)  # 16GB available
	print("   💾 Model compatibility (assuming 16GB available memory):")
	for model_name, can_run in compatibility.items():
		status = "✅" if can_run else "❌"
		print(f"      {status} {model_name}")
	print()
	
	print("🎉 All tests passed! Centralized configuration working correctly.")
	print()
	print("📋 SUMMARY:")
	print(f"   • Universal Planner: {planner.name}")
	print(f"   • Tier 1 Primary: {primary_text.name}")
	print(f"   • Tier 2 Primary: {primary_vision.name}") 
	print(f"   • Tier 3 Primary: {primary_cloud.name}")
	print(f"   • Text escalation: {len(text_chain)} tiers")
	print(f"   • Vision escalation: {len(vision_chain)} tiers")
	print()
	print("✨ To change models, edit ONLY /browser-agent/config/central_model_config.py")
	
	return True


def demo_routing_scenarios():
	"""Demo common routing scenarios."""
	print()
	print("🎭 Routing Scenario Demonstrations")
	print("=" * 60)
	
	scenarios = [
		{
			"name": "Simple Navigation",
			"requires_vision": False,
			"description": "Navigate to google.com and search for 'python'"
		},
		{
			"name": "Visual Element Search", 
			"requires_vision": True,
			"description": "Find the blue 'Sign In' button on the page"
		},
		{
			"name": "Complex Multi-Step Task",
			"requires_vision": True,
			"description": "Research competitors, analyze pricing tables, and create comparison"
		}
	]
	
	for i, scenario in enumerate(scenarios, 1):
		print(f"{i}️⃣ Scenario: {scenario['name']}")
		print(f"   📝 Task: {scenario['description']}")
		
		# Show routing decision
		escalation_chain = get_escalation_chain(requires_vision=scenario["requires_vision"])
		starting_tier = escalation_chain[0]
		primary_model = get_primary_model(starting_tier)
		
		print(f"   🎯 Starting tier: {starting_tier.value}")
		print(f"   🤖 Primary model: {primary_model.name}")
		print(f"   🔄 Escalation path: {' → '.join([t.value for t in escalation_chain])}")
		print()
	
	print("✨ All routing decisions use the same centralized configuration!")


if __name__ == "__main__":
	print()
	success = test_centralized_configuration()
	
	if success:
		demo_routing_scenarios()
	else:
		print("❌ Tests failed!")
		sys.exit(1)
	
	print()
	print("🎯 Next Steps:")
	print("   1. Update any remaining hardcoded model references")
	print("   2. Test with real model handlers (local + cloud)")
	print("   3. Monitor routing decisions in production")
	print()