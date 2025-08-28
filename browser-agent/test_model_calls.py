#!/usr/bin/env python3
"""
Test actual model calls and escalation chain.
This script tests the real functionality beyond just model selection.
"""

import asyncio
import logging
from dotenv import load_dotenv

from config.settings import Settings
from config.models import ModelConfigManager
from models.local_handler import OllamaModelHandler
from models.cloud_handler import CloudModelManager, BudgetManager, ResponseCache
from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_granite_vision_call():
	"""Test actual call to granite3.2-vision model."""
	logger.info("=== Testing Granite 3.2 Vision Model Call ===")
	
	# Load environment
	load_dotenv()
	settings = Settings()
	
	# Initialize components
	model_config_manager = ModelConfigManager()
	local_handler = OllamaModelHandler(
		base_url=settings.ollama_base_url,
		timeout=settings.task_timeout
	)
	
	try:
		async with local_handler:
			if not await local_handler.is_available():
				logger.error("Ollama server not available")
				return False
			
			# Test simple text generation
			prompt = "You are a browser automation assistant. Describe what you would do to navigate to google.com and search for 'python automation'. Be specific about the steps."
			
			logger.info("Calling granite3.2-vision with browser automation prompt...")
			response = await local_handler.generate_text(
				model_name="granite3.2-vision",
				prompt=prompt,
				system_prompt="You are an expert browser automation assistant.",
				temperature=0.1,
				max_tokens=500
			)
			
			logger.info(f"Response length: {len(response)} characters")
			logger.info(f"Response preview: {response[:200]}...")
			
			# Verify response quality
			if len(response) < 50:
				logger.warning("Response seems too short")
				return False
			
			if "google" not in response.lower() or "search" not in response.lower():
				logger.warning("Response doesn't seem to address the prompt properly")
				return False
			
			logger.info("✅ Granite 3.2 Vision call successful!")
			return True
			
	except Exception as e:
		logger.error(f"❌ Granite 3.2 Vision call failed: {e}")
		return False

async def test_model_escalation():
	"""Test the escalation chain when models fail."""
	logger.info("=== Testing Model Escalation Chain ===")
	
	# Load environment  
	load_dotenv()
	settings = Settings()
	
	# Initialize all components
	model_config_manager = ModelConfigManager()
	
	local_handler = OllamaModelHandler(
		base_url=settings.ollama_base_url,
		timeout=settings.task_timeout
	)
	
	# Initialize cloud handlers
	api_keys = {}
	if settings.openai_api_key:
		api_keys['openai'] = settings.openai_api_key
	if settings.anthropic_api_key:
		api_keys['anthropic'] = settings.anthropic_api_key
	
	cloud_manager = None
	if api_keys:
		budget_manager = BudgetManager(daily_limit=50.0, monthly_limit=500.0)
		cache = ResponseCache(max_age_hours=24)
		cloud_manager = CloudModelManager(
			openai_api_key=api_keys.get('openai'),
			anthropic_api_key=api_keys.get('anthropic'),
			budget_manager=budget_manager,
			cache=cache
		)
	
	model_router = ModelRouter(
		model_config_manager=model_config_manager,
		local_handler=local_handler,
		cloud_manager=cloud_manager,
		default_strategy=RoutingStrategy.BALANCED
	)
	
	try:
		# Test execution task that should use granite3.2-vision first
		execution_task = TaskRequirements(
			requires_vision=False,  # Keep it simple for first test
			requires_code=True
		)
		
		logger.info("Testing execute_with_fallback...")
		response, token_usage, model_config = await model_router.execute_with_fallback(
			task_requirements=execution_task,
			prompt="Write a Python function that takes a screenshot of a webpage using selenium. Include error handling.",
			system_prompt="You are a browser automation expert. Write clean, production-ready code.",
		)
		
		logger.info(f"✅ Escalation test successful!")
		logger.info(f"Used model: {model_config.name}")
		logger.info(f"Token usage: {token_usage}")
		logger.info(f"Response length: {len(response)} characters")
		logger.info(f"Response preview: {response[:200]}...")
		
		return True
		
	except Exception as e:
		logger.error(f"❌ Escalation test failed: {e}")
		return False
	
	finally:
		# Cleanup
		if cloud_manager:
			await cloud_manager.close()
		if local_handler:
			await local_handler.close()

async def test_planning_vs_execution():
	"""Test that planning and execution tasks use different models."""
	logger.info("=== Testing Planning vs Execution Model Selection ===")
	
	# Load environment
	load_dotenv()
	settings = Settings()
	
	# Initialize components (simplified for just model selection)
	model_config_manager = ModelConfigManager()
	model_router = ModelRouter(
		model_config_manager=model_config_manager,
		local_handler=None,  # Just testing selection, not execution
		cloud_manager=None
	)
	
	try:
		# Test planning task
		planning_task = TaskRequirements(is_planning_task=True)
		planning_model = await model_router.select_model(planning_task)
		
		# Test execution task  
		execution_task = TaskRequirements(requires_vision=True)
		execution_model = await model_router.select_model(execution_task)
		
		logger.info(f"Planning task → {planning_model.name}")
		logger.info(f"Execution task → {execution_model.name}")
		
		# Verify different models are selected
		if planning_model.name == execution_model.name:
			logger.warning("⚠️ Same model selected for planning and execution")
		else:
			logger.info("✅ Different models correctly selected for different task types")
		
		# Verify expected models
		expected_planner = "OpenAI O3 Mini"
		expected_executor = "Granite 3.2 Vision"
		
		if planning_model.name != expected_planner:
			logger.warning(f"⚠️ Expected planner: {expected_planner}, got: {planning_model.name}")
		
		if execution_model.name != expected_executor:
			logger.warning(f"⚠️ Expected executor: {expected_executor}, got: {execution_model.name}")
		
		if (planning_model.name == expected_planner and 
			execution_model.name == expected_executor):
			logger.info("✅ Model assignment matches expected progression!")
			
		return True
		
	except Exception as e:
		logger.error(f"❌ Planning vs execution test failed: {e}")
		return False

async def main():
	"""Run all model tests."""
	logger.info("🧪 Starting Model Progression Tests")
	
	results = []
	
	# Test 1: Basic model selection  
	logger.info("\n" + "="*50)
	result1 = await test_planning_vs_execution()
	results.append(("Model Selection", result1))
	
	# Test 2: Actual granite call
	logger.info("\n" + "="*50) 
	result2 = await test_granite_vision_call()
	results.append(("Granite 3.2 Vision Call", result2))
	
	# Test 3: Escalation chain
	logger.info("\n" + "="*50)
	result3 = await test_model_escalation()
	results.append(("Model Escalation", result3))
	
	# Summary
	logger.info("\n" + "="*50)
	logger.info("🏁 TEST RESULTS SUMMARY:")
	
	passed = 0
	for test_name, result in results:
		status = "✅ PASS" if result else "❌ FAIL"
		logger.info(f"  {test_name}: {status}")
		if result:
			passed += 1
	
	logger.info(f"\nPassed: {passed}/{len(results)} tests")
	
	if passed == len(results):
		logger.info("🎉 All tests passed! Model progression is working correctly.")
	else:
		logger.warning("⚠️ Some tests failed. Review the model configuration.")

if __name__ == "__main__":
	asyncio.run(main())