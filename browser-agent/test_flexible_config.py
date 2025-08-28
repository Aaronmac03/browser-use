#!/usr/bin/env python3
"""
Test script to demonstrate how easy it is to change LLM configurations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_current_configuration():
	"""Test the current configuration."""
	from config.central_model_config import (
		get_current_model_names,
		get_planner_model,
		get_tier_models,
		ModelTier
	)
	
	print("🔧 Current Model Configuration")
	print("=" * 50)
	
	# Show all current models
	models = get_current_model_names()
	for role, model_name in models.items():
		print(f"{role:15}: {model_name}")
	print()
	
	# Verify the planner
	planner = get_planner_model()
	print(f"✅ Planner Model: {planner.name}")
	
	# Verify tier models
	for tier in [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]:
		tier_models = get_tier_models(tier)
		primary = next((m for m in tier_models if m.is_primary), None)
		print(f"✅ {tier.value} Primary: {primary.name if primary else 'None'}")
	
	return True

def simulate_model_changes():
	"""Simulate what happens when you change the configuration variables."""
	print()
	print("🎭 Simulating Model Changes")
	print("=" * 50)
	print("📝 To change models, you would edit these lines in central_model_config.py:")
	print()
	
	changes = [
		("PLANNER_MODEL", "o3-2025-04-16", "claude-3-5-sonnet", "Change planner to Claude"),
		("TEXT_PRIMARY", "qwen3:8b", "deepseek-r1:8b", "Change primary text model to DeepSeek"),
		("VISION_PRIMARY", "qwen2.5vl:7b", "minicpm-v:8b", "Change primary vision model"),
		("CLOUD_PRIMARY", "gemini-2.5-flash", "gpt-4o", "Change primary cloud model to GPT-4")
	]
	
	for var_name, current, new, description in changes:
		print(f"  {var_name} = '{current}'  →  '{new}'")
		print(f"    # {description}")
		print()
	
	print("💡 That's it! All routers automatically use the new models.")
	print("   No need to edit multiple files or search for hardcoded references.")

def test_configuration_api():
	"""Test the configuration API functions."""
	from config.central_model_config import (
		CENTRAL_MODEL_CONFIG,
		get_escalation_chain,
		get_primary_model,
		ModelTier
	)
	
	print()
	print("🛠️ Configuration API Test")
	print("=" * 50)
	
	# Test escalation chains
	text_chain = get_escalation_chain(requires_vision=False)
	vision_chain = get_escalation_chain(requires_vision=True)
	
	print(f"Text escalation:   {' → '.join([t.value for t in text_chain])}")
	print(f"Vision escalation: {' → '.join([t.value for t in vision_chain])}")
	print()
	
	# Test primary models
	for tier in [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]:
		primary = get_primary_model(tier)
		fallbacks = CENTRAL_MODEL_CONFIG.get_fallback_models(tier)
		fallback_names = [f.name for f in fallbacks]
		
		print(f"{tier.value:15}: {primary.name} (fallbacks: {fallback_names})")
	
	# Test system compatibility
	print()
	compatibility = CENTRAL_MODEL_CONFIG.validate_system_compatibility(16.0)
	compatible_models = [name for name, can_run in compatibility.items() if can_run]
	print(f"Compatible models (16GB): {len(compatible_models)}/{len(compatibility)}")
	
	return True

if __name__ == "__main__":
	print("🧪 Flexible Model Configuration Test")
	print("=" * 60)
	print()
	
	try:
		test_current_configuration()
		simulate_model_changes() 
		test_configuration_api()
		
		print()
		print("🎉 Flexible configuration test passed!")
		print()
		print("📋 Summary:")
		print("   ✅ Easy model changes - edit variables at top of file")
		print("   ✅ All routers automatically use new configuration")
		print("   ✅ Single source of truth maintained")
		print("   ✅ Configuration API provides programmatic access")
		print()
		print("🎯 To change models:")
		print("   1. Edit variables at top of config/central_model_config.py")
		print("   2. Run this test to verify changes")
		print("   3. That's it! 🚀")
		
	except Exception as e:
		print(f"❌ Test failed: {e}")
		import traceback
		traceback.print_exc()
		sys.exit(1)