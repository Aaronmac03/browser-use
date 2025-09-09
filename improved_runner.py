#!/usr/bin/env python3
"""
Improved Runner - Integration of All Enhancements
================================================

Integrates all the improvements:
1. Improved browser session management
2. Enhanced schema transformation
3. Better result validation
4. Robust error handling and recovery
5. Performance monitoring and optimization
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
import httpx

# Import browser-use components
from browser_use import Agent, Browser, ChatOpenAI, ChatLlamaCpp, Tools
from browser_use.llm.base import BaseChatModel
from browser_use.agent.views import ActionResult
from browser_use.llm.messages import SystemMessage, UserMessage

# Import our improvements
from improved_browser_session import ImprovedBrowserSession, BrowserHealthChecker
from improved_schema_handler import ImprovedSchemaHandler, transform_llm_response
from improved_result_validator import (
	ImprovedResultValidator, ValidationCriteria, ValidationEvidence, 
	ValidationResult, create_validation_criteria, create_validation_evidence
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TaskExecutionResult:
	"""Result of task execution with comprehensive data."""
	success: bool
	execution_time: float
	subtasks_completed: int
	total_subtasks: int
	validation_result: ValidationResult
	validation_confidence: float
	actions_taken: List[str]
	errors_encountered: List[str]
	final_url: Optional[str]
	final_content: Optional[str]
	cloud_api_calls: int
	local_llm_calls: int
	recommendations: List[str]

class ImprovedRunner:
	"""
	Enhanced runner with all improvements integrated.
	
	Key features:
	- Robust browser session management
	- Intelligent schema transformation
	- Evidence-based result validation
	- Performance monitoring
	- Privacy-first architecture
	"""
	
	def __init__(self):
		self.schema_handler = ImprovedSchemaHandler()
		self.result_validator = ImprovedResultValidator()
		self.browser_session: Optional[ImprovedBrowserSession] = None
		self.health_checker: Optional[BrowserHealthChecker] = None
		
		# Performance tracking
		self.performance_stats = {
			'total_tasks': 0,
			'successful_tasks': 0,
			'cloud_api_calls': 0,
			'local_llm_calls': 0,
			'total_execution_time': 0.0,
			'browser_restarts': 0
		}
	
	async def execute_task(self, goal: str, **kwargs) -> TaskExecutionResult:
		"""
		Execute a task with all improvements applied.
		
		Args:
			goal: Task description
			**kwargs: Additional configuration options
			
		Returns:
			TaskExecutionResult with comprehensive execution data
		"""
		start_time = time.time()
		self.performance_stats['total_tasks'] += 1
		
		logger.info(f"[TASK] Starting improved execution: {goal}")
		
		try:
			# Step 1: Initialize browser session
			await self._ensure_browser_session()
			
			# Step 2: Plan task with cloud LLM
			subtasks = await self._plan_task_with_cloud(goal)
			logger.info(f"[PLAN] Generated {len(subtasks)} subtasks")
			
			# Step 3: Execute subtasks with local LLM
			execution_results = []
			for i, subtask in enumerate(subtasks):
				logger.info(f"[SUBTASK] Executing {i+1}/{len(subtasks)}: {subtask['title']}")
				
				subtask_result = await self._execute_subtask_improved(subtask, goal)
				execution_results.append(subtask_result)
				
				# Break on critical failure
				if not subtask_result['success'] and subtask_result.get('critical_failure', False):
					logger.error(f"[SUBTASK] Critical failure, stopping execution")
					break
			
			# Step 4: Validate overall results
			validation_result = await self._validate_task_completion(goal, execution_results)
			
			# Step 5: Compile final result
			execution_time = time.time() - start_time
			final_result = self._compile_final_result(
				goal, execution_results, validation_result, execution_time
			)
			
			# Step 6: Update performance stats
			self._update_performance_stats(final_result)
			
			logger.info(f"[TASK] Completed in {execution_time:.1f}s - Success: {final_result.success}")
			return final_result
			
		except Exception as e:
			logger.error(f"[TASK] Execution failed: {e}")
			execution_time = time.time() - start_time
			
			return TaskExecutionResult(
				success=False,
				execution_time=execution_time,
				subtasks_completed=0,
				total_subtasks=0,
				validation_result=ValidationResult.FAILURE,
				validation_confidence=0.0,
				actions_taken=[],
				errors_encountered=[str(e)],
				final_url=None,
				final_content=None,
				cloud_api_calls=self.performance_stats['cloud_api_calls'],
				local_llm_calls=self.performance_stats['local_llm_calls'],
				recommendations=[f"Task failed with error: {e}"]
			)
	
	async def _ensure_browser_session(self):
		"""Ensure browser session is healthy and ready."""
		if not self.browser_session:
			logger.info("[BROWSER] Creating new browser session...")
			self.browser_session = ImprovedBrowserSession(
				executable_path=self._get_chrome_executable(),
				user_data_dir=os.getenv("CHROME_USER_DATA_DIR"),
				profile_directory=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
				headless=os.getenv("HEADLESS", "false").lower() == "true"
			)
			await self.browser_session.start()
			
			# Create health checker
			session = await self.browser_session.get_session()
			self.health_checker = BrowserHealthChecker(session)
		
		else:
			# Check if restart is needed
			if self.health_checker:
				health_status = await self.health_checker.check_health()
				if self.health_checker.should_restart(health_status):
					logger.info("[BROWSER] Restarting unhealthy browser session...")
					await self.browser_session.restart_if_needed()
					self.performance_stats['browser_restarts'] += 1
	
	def _get_chrome_executable(self) -> Optional[str]:
		"""Get Chrome executable path."""
		# Try environment variable first
		chrome_path = os.getenv("CHROME_EXECUTABLE_PATH")
		if chrome_path and os.path.exists(chrome_path):
			return chrome_path
		
		# Try common Windows paths
		common_paths = [
			r"C:\Program Files\Google\Chrome\Application\chrome.exe",
			r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
			r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv("USERNAME", ""))
		]
		
		for path in common_paths:
			if os.path.exists(path):
				return path
		
		return None
	
	async def _plan_task_with_cloud(self, goal: str) -> List[Dict[str, Any]]:
		"""Plan task using cloud LLM with improved prompting."""
		self.performance_stats['cloud_api_calls'] += 1
		
		# Enhanced planning prompt
		planning_prompt = f"""
		You are an expert planner for browser automation using a local 7B LLM executor.
		
		EXECUTOR CONSTRAINTS:
		- Local Qwen2.5-7B model optimized for single, focused actions
		- Best performance with 1-2 actions per subtask
		- 10-20 second response time per action
		- Prefers direct navigation over complex exploration
		
		PLANNING STRATEGY:
		- Break complex tasks into atomic single-action subtasks
		- Each subtask should have ONE clear, verifiable action
		- Use web_search tool for discovery before navigation
		- Provide specific, actionable instructions
		- Include clear success criteria for validation
		
		GOAL: {goal}
		
		Create a plan with atomic subtasks. Return JSON:
		{{
			"subtasks": [
				{{
					"title": "Single action description",
					"instructions": "Specific step-by-step instructions",
					"success_criteria": "Specific evidence of completion",
					"estimated_time": 30,
					"requires_web_search": false
				}}
			]
		}}
		"""
		
		try:
			# Try OpenAI first
			llm = self._create_cloud_llm()
			response = await llm.ainvoke([
				SystemMessage(content="You are an expert browser automation planner."),
				UserMessage(content=planning_prompt)
			])
			
			# Extract JSON from response
			response_text = response.completion
			json_start = response_text.find('{')
			json_end = response_text.rfind('}') + 1
			
			if json_start >= 0 and json_end > json_start:
				plan_data = json.loads(response_text[json_start:json_end])
				return plan_data.get('subtasks', [])
			
		except Exception as e:
			logger.warning(f"[PLAN] Cloud planning failed: {e}")
		
		# Fallback: Create simple plan
		return [{
			"title": "Execute task directly",
			"instructions": f"Complete the following task: {goal}",
			"success_criteria": "Task completed successfully",
			"estimated_time": 120,
			"requires_web_search": True
		}]
	
	def _create_cloud_llm(self) -> BaseChatModel:
		"""Create cloud LLM for planning."""
		model = os.getenv("OPENAI_MODEL", "gpt-4")
		return ChatOpenAI(
			model=model,
			temperature=0.2,
			timeout=60
		)
	
	def _create_local_llm(self) -> BaseChatModel:
		"""Create local LLM for execution."""
		base_url = os.getenv("LLAMACPP_HOST", "http://localhost:8080")
		model = "qwen2.5-14b-instruct-q4_k_m.gguf"
		
		return ChatLlamaCpp(
			model=model,
			base_url=base_url,
			timeout=60,
			temperature=0.1,
			max_tokens=4096
		)
	
	async def _execute_subtask_improved(self, subtask: Dict[str, Any], overall_goal: str) -> Dict[str, Any]:
		"""Execute a single subtask with all improvements."""
		start_time = time.time()
		self.performance_stats['local_llm_calls'] += 1
		
		try:
			# Create tools for this subtask
			tools = self._create_enhanced_tools(subtask)
			
			# Create local LLM agent
			local_llm = self._create_local_llm()
			browser_session = await self.browser_session.get_session()
			
			# Enhanced agent prompt
			agent_prompt = f"""
			You are a browser automation agent executing a specific subtask.
			
			OVERALL GOAL: {overall_goal}
			CURRENT SUBTASK: {subtask['title']}
			INSTRUCTIONS: {subtask['instructions']}
			SUCCESS CRITERIA: {subtask['success_criteria']}
			
			EXECUTION GUIDELINES:
			- Focus on ONE specific action per step
			- Use web_search tool for discovery when needed
			- Navigate directly to target sites when possible
			- Verify success criteria before completing
			- Use 'done' action only when criteria are clearly met
			
			Execute this subtask efficiently and report completion when success criteria are met.
			"""
			
			# Create agent
			agent = Agent(
				task=agent_prompt,
				llm=local_llm,
				browser=browser_session,
				tools=tools
			)
			
			# Execute with timeout
			timeout = subtask.get('estimated_time', 120)
			agent_result = await asyncio.wait_for(
				agent.run(),
				timeout=timeout
			)
			
			# Transform schema if needed
			if hasattr(agent_result, 'completion'):
				transformed_result = self.schema_handler.transform_llm_output(agent_result.completion)
				if transformed_result.success:
					logger.info(f"[SCHEMA] Applied transformations: {transformed_result.transformations_applied}")
			
			# Collect execution evidence
			evidence = await self._collect_execution_evidence(browser_session, start_time)
			
			# Validate subtask completion
			validation_criteria = create_validation_criteria(
				task_description=subtask['title'],
				success_indicators=subtask['success_criteria'].split(','),
				timeout=timeout
			)
			
			validation_result, validation_analysis = self.result_validator.validate_task_result(
				validation_criteria, evidence, agent_result.__dict__ if hasattr(agent_result, '__dict__') else None
			)
			
			execution_time = time.time() - start_time
			
			return {
				'success': validation_result in [ValidationResult.SUCCESS, ValidationResult.PARTIAL_SUCCESS],
				'validation_result': validation_result,
				'validation_confidence': validation_analysis['confidence_score'],
				'execution_time': execution_time,
				'actions_taken': evidence.actions_taken,
				'errors_encountered': evidence.errors_encountered,
				'final_url': evidence.url,
				'recommendations': validation_analysis['recommendations'],
				'critical_failure': validation_result == ValidationResult.TIMEOUT
			}
			
		except asyncio.TimeoutError:
			execution_time = time.time() - start_time
			logger.error(f"[SUBTASK] Timeout after {execution_time:.1f}s")
			
			return {
				'success': False,
				'validation_result': ValidationResult.TIMEOUT,
				'validation_confidence': 0.0,
				'execution_time': execution_time,
				'actions_taken': [],
				'errors_encountered': ['Subtask timeout'],
				'final_url': None,
				'recommendations': ['Increase timeout or simplify subtask'],
				'critical_failure': True
			}
			
		except Exception as e:
			execution_time = time.time() - start_time
			logger.error(f"[SUBTASK] Execution error: {e}")
			
			return {
				'success': False,
				'validation_result': ValidationResult.FAILURE,
				'validation_confidence': 0.0,
				'execution_time': execution_time,
				'actions_taken': [],
				'errors_encountered': [str(e)],
				'final_url': None,
				'recommendations': [f'Fix execution error: {e}'],
				'critical_failure': False
			}
	
	def _create_enhanced_tools(self, subtask: Dict[str, Any]) -> Tools:
		"""Create enhanced tools for subtask execution."""
		tools = Tools()
		
		# Web search tool
		@tools.action(description="Search the web for information. Use before navigating to unknown sites.")
		def web_search(query: str, num_results: int = 5) -> str:
			serper_key = os.getenv("SERPER_API_KEY")
			if not serper_key:
				return json.dumps({"error": "SERPER_API_KEY not set"})
			
			try:
				payload = {"q": query, "num": min(num_results, 10)}
				headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
				response = httpx.post(
					"https://google.serper.dev/search",
					headers=headers,
					json=payload,
					timeout=30
				)
				response.raise_for_status()
				
				data = response.json()
				results = []
				for item in data.get("organic", [])[:num_results]:
					results.append({
						"title": item.get("title", ""),
						"link": item.get("link", ""),
						"snippet": item.get("snippet", "")
					})
				
				return json.dumps({"query": query, "results": results})
				
			except Exception as e:
				return json.dumps({"error": str(e)})
		
		return tools
	
	async def _collect_execution_evidence(self, browser_session, start_time: float) -> ValidationEvidence:
		"""Collect evidence from browser session for validation."""
		try:
			# Get current browser state
			# This is a simplified version - in real implementation,
			# you'd use browser_session methods to get actual state
			
			evidence = ValidationEvidence(
				url="about:blank",  # Placeholder
				title="",  # Placeholder
				page_text="",  # Placeholder
				execution_time=time.time() - start_time,
				actions_taken=[],  # Would be collected during execution
				errors_encountered=[]  # Would be collected during execution
			)
			
			return evidence
			
		except Exception as e:
			logger.warning(f"[EVIDENCE] Failed to collect evidence: {e}")
			return ValidationEvidence(
				execution_time=time.time() - start_time,
				errors_encountered=[f"Evidence collection failed: {e}"]
			)
	
	async def _validate_task_completion(self, goal: str, execution_results: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""Validate overall task completion."""
		# Extract success indicators from goal
		success_indicators = self._extract_success_indicators(goal)
		
		# Create overall validation criteria
		criteria = create_validation_criteria(
			task_description=goal,
			success_indicators=success_indicators,
			timeout=300.0  # Overall task timeout
		)
		
		# Aggregate evidence from all subtasks
		total_execution_time = sum(result['execution_time'] for result in execution_results)
		all_actions = []
		all_errors = []
		final_url = None
		
		for result in execution_results:
			all_actions.extend(result.get('actions_taken', []))
			all_errors.extend(result.get('errors_encountered', []))
			if result.get('final_url'):
				final_url = result['final_url']
		
		evidence = create_validation_evidence(
			url=final_url,
			actions=all_actions,
			errors=all_errors,
			execution_time=total_execution_time
		)
		
		# Validate overall completion
		validation_result, validation_analysis = self.result_validator.validate_task_result(
			criteria, evidence
		)
		
		return {
			'validation_result': validation_result,
			'validation_analysis': validation_analysis,
			'subtasks_successful': sum(1 for r in execution_results if r['success']),
			'total_subtasks': len(execution_results)
		}
	
	def _extract_success_indicators(self, goal: str) -> List[str]:
		"""Extract success indicators from goal description."""
		# Simple keyword extraction - can be enhanced
		import re
		
		# Look for specific patterns that indicate success criteria
		indicators = []
		
		# Extract quoted terms
		quoted_terms = re.findall(r'"([^"]*)"', goal)
		indicators.extend(quoted_terms)
		
		# Extract key nouns and verbs
		words = re.findall(r'\b\w{4,}\b', goal.lower())
		
		# Filter for likely success indicators
		success_words = [
			'weather', 'temperature', 'price', 'cost', 'tutorial', 'guide',
			'news', 'article', 'post', 'review', 'information', 'data',
			'result', 'search', 'find', 'locate', 'discover'
		]
		
		for word in words:
			if word in success_words:
				indicators.append(word)
		
		# Remove duplicates and limit
		return list(set(indicators))[:5]
	
	def _compile_final_result(
		self,
		goal: str,
		execution_results: List[Dict[str, Any]],
		validation_result: Dict[str, Any],
		execution_time: float
	) -> TaskExecutionResult:
		"""Compile final task execution result."""
		successful_subtasks = sum(1 for r in execution_results if r['success'])
		total_subtasks = len(execution_results)
		
		# Aggregate data
		all_actions = []
		all_errors = []
		all_recommendations = []
		final_url = None
		
		for result in execution_results:
			all_actions.extend(result.get('actions_taken', []))
			all_errors.extend(result.get('errors_encountered', []))
			all_recommendations.extend(result.get('recommendations', []))
			if result.get('final_url'):
				final_url = result['final_url']
		
		# Add validation recommendations
		all_recommendations.extend(
			validation_result['validation_analysis'].get('recommendations', [])
		)
		
		# Determine overall success
		overall_success = (
			validation_result['validation_result'] in [ValidationResult.SUCCESS, ValidationResult.PARTIAL_SUCCESS] and
			successful_subtasks >= total_subtasks * 0.8  # At least 80% subtasks successful
		)
		
		return TaskExecutionResult(
			success=overall_success,
			execution_time=execution_time,
			subtasks_completed=successful_subtasks,
			total_subtasks=total_subtasks,
			validation_result=validation_result['validation_result'],
			validation_confidence=validation_result['validation_analysis']['confidence_score'],
			actions_taken=all_actions,
			errors_encountered=all_errors,
			final_url=final_url,
			final_content=None,  # Could be extracted if needed
			cloud_api_calls=self.performance_stats['cloud_api_calls'],
			local_llm_calls=self.performance_stats['local_llm_calls'],
			recommendations=list(set(all_recommendations))  # Remove duplicates
		)
	
	def _update_performance_stats(self, result: TaskExecutionResult):
		"""Update performance statistics."""
		if result.success:
			self.performance_stats['successful_tasks'] += 1
		
		self.performance_stats['total_execution_time'] += result.execution_time
	
	async def cleanup(self):
		"""Clean up resources."""
		if self.browser_session:
			await self.browser_session.close()
			self.browser_session = None
			self.health_checker = None
	
	def get_performance_stats(self) -> Dict[str, Any]:
		"""Get current performance statistics."""
		total_tasks = self.performance_stats['total_tasks']
		success_rate = (
			self.performance_stats['successful_tasks'] / total_tasks 
			if total_tasks > 0 else 0.0
		)
		
		avg_execution_time = (
			self.performance_stats['total_execution_time'] / total_tasks
			if total_tasks > 0 else 0.0
		)
		
		return {
			'total_tasks': total_tasks,
			'successful_tasks': self.performance_stats['successful_tasks'],
			'success_rate': f"{success_rate:.1%}",
			'average_execution_time': f"{avg_execution_time:.1f}s",
			'cloud_api_calls': self.performance_stats['cloud_api_calls'],
			'local_llm_calls': self.performance_stats['local_llm_calls'],
			'browser_restarts': self.performance_stats['browser_restarts'],
			'schema_transformation_stats': self.schema_handler.get_transformation_stats(),
			'validation_stats': self.result_validator.get_validation_stats()
		}


# Main execution function
async def main(goal: str) -> TaskExecutionResult:
	"""Main execution function with improved runner."""
	load_dotenv()
	
	runner = ImprovedRunner()
	try:
		result = await runner.execute_task(goal)
		
		# Print performance summary
		stats = runner.get_performance_stats()
		logger.info(f"[STATS] Performance Summary:")
		logger.info(f"  Success Rate: {stats['success_rate']}")
		logger.info(f"  Avg Execution Time: {stats['average_execution_time']}")
		logger.info(f"  Cloud API Calls: {stats['cloud_api_calls']}")
		logger.info(f"  Local LLM Calls: {stats['local_llm_calls']}")
		
		return result
		
	finally:
		await runner.cleanup()


if __name__ == "__main__":
	import sys
	
	if len(sys.argv) < 2:
		print("Usage: python improved_runner.py \"<task description>\"")
		sys.exit(1)
	
	goal = sys.argv[1]
	result = asyncio.run(main(goal))
	
	print(f"\n{'='*60}")
	print(f"TASK EXECUTION SUMMARY")
	print(f"{'='*60}")
	print(f"Goal: {goal}")
	print(f"Success: {result.success}")
	print(f"Execution Time: {result.execution_time:.1f}s")
	print(f"Subtasks: {result.subtasks_completed}/{result.total_subtasks}")
	print(f"Validation: {result.validation_result.value} ({result.validation_confidence:.2f})")
	print(f"Actions Taken: {len(result.actions_taken)}")
	print(f"Errors: {len(result.errors_encountered)}")
	
	if result.recommendations:
		print(f"\nRecommendations:")
		for rec in result.recommendations[:3]:  # Top 3 recommendations
			print(f"  • {rec}")
	
	sys.exit(0 if result.success else 1)