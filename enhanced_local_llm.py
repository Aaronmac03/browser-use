#!/usr/bin/env python3
"""
Enhanced Local LLM Configuration using llama.cpp
Optimized for privacy-first, reliable web navigation with cloud planning support.
Updated to use llama.cpp server instead of Ollama for better performance and control.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatOpenAI, ChatLlamaCpp, Tools
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from browser_use.agent.views import ActionResult

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class LocalLLMConfig:
	"""Optimized configuration for Windows PC with GTX 1660 Ti local LLM usage."""
	
	# Model preferences (ordered by speed/reliability)
	preferred_models: List[str] = None
	fallback_models: List[str] = None
	
	# Performance settings - optimized for GTX 1660 Ti
	max_actions_per_step: int = 1  # Single actions for precision
	max_history_items: int = 6     # Minimal context for speed
	step_timeout: int = 45         # Faster timeout for GPU acceleration
	max_failures: int = 3          # Allow retries with recovery
	
	# Memory management - optimized for 16GB RAM + 6GB VRAM
	use_thinking: bool = True      # Enable reasoning
	use_vision: bool = False       # Disable for performance
	
	# Prompt optimization
	use_specialized_prompts: bool = True
	include_navigation_patterns: bool = True
	
	# GPU acceleration settings
	enable_gpu_acceleration: bool = True
	gpu_memory_fraction: float = 0.8  # Use 80% of VRAM
	batch_processing: bool = True     # Enable batch processing
	
	# Response optimization
	temperature: float = 0.1          # Low temperature for consistency
	max_tokens: int = 2048           # Reduced for faster responses
	top_p: float = 0.9               # Nucleus sampling
	
	# Hardware-specific optimizations
	hardware_profile: str = "gtx_1660_ti"  # Hardware profile identifier
	
	def __post_init__(self):
		if self.preferred_models is None:
			# Optimized for Windows PC i7-9750H + GTX 1660 Ti (6GB VRAM)
			self.preferred_models = [
				"qwen2.5-7b-instruct-q4_k_m",    # Best for GPU acceleration
				"qwen2.5-coder:7b",              # For technical tasks
				"llama3.1:8b",                   # For complex reasoning
			]
		
		if self.fallback_models is None:
			# Only if 7B unavailable
			self.fallback_models = [
				"qwen2.5:14b-instruct-q4_k_m",
				"qwen2.5:14b-instruct",
				"llama3.2:3b-instruct-q4_k_m",  # Ultra-fast fallback
			]

class OptimizedLocalLLM:
	"""Enhanced local LLM client with Windows PC + GTX 1660 Ti optimizations."""
	
	def __init__(self, config: LocalLLMConfig = None):
		self.config = config or LocalLLMConfig()
		self.host = os.getenv("LLAMACPP_HOST", "http://localhost:8080")
		self._client = None
		self._selected_model = None
		# Windows console compatibility
		self.use_emoji = False  # Disable emojis for Windows console
	
	async def get_optimized_client(self) -> BaseChatModel:
		"""Get the best available local LLM client."""
		if self._client is not None:
			return self._client
		
		model = await self._select_best_model()
		
		# Optimized client configuration for GTX 1660 Ti
		self._client = ChatLlamaCpp(
			model=model,
			base_url=self.host,
			timeout=self.config.step_timeout,
			temperature=self.config.temperature,
			max_tokens=self.config.max_tokens,
			top_p=self.config.top_p,
			# Additional performance optimizations
			request_timeout=self.config.step_timeout,
			max_retries=2,
		)
		
		logger.info(f"[READY] Optimized local LLM ready: {model}")
		return self._client
	
	async def _select_best_model(self) -> str:
		"""Intelligently select the best available model for llama.cpp."""
		try:
			import httpx
			# Test if llama.cpp server is running
			async with httpx.AsyncClient() as client:
				response = await client.get(f"{self.host}/health", timeout=5)
				if response.status_code == 200:
					logger.info("[INFO] llama.cpp server is running")
				else:
					logger.warning(f"[WARN] llama.cpp server responded with status {response.status_code}")
			
			# For llama.cpp, we use the first preferred model since the server loads one model at a time
			for model in self.config.preferred_models:
				self._selected_model = model
				logger.info(f"[SUCCESS] Selected model for llama.cpp: {model}")
				return model
			
		except Exception as e:
			logger.error(f"[ERROR] llama.cpp server connection failed: {e}")
		
		# Default fallback
		self._selected_model = "qwen2.5-7b-instruct-q4_k_m"
		logger.info(f"[INFO] Using default model: {self._selected_model}")
		return self._selected_model
	
	def create_optimized_agent(
		self,
		task: str,
		browser: Browser,
		tools: Tools,
		step_number: int = 1,
		total_steps: int = 1,
		**kwargs
	) -> Agent:
		"""Create an agent optimized for local LLM execution."""
		
		# Specialized system prompt for web navigation
		system_prompt = self._build_navigation_prompt(
			task, step_number, total_steps
		)
		
		return Agent(
			task=task,
			llm=self._client,
			browser=browser,
			tools=tools,
			# Optimized settings for local LLM
			use_thinking=self.config.use_thinking,
			use_vision=self.config.use_vision,
			max_actions_per_step=self.config.max_actions_per_step,
			max_history_items=self.config.max_history_items,
			step_timeout=self.config.step_timeout,
			max_failures=self.config.max_failures,
			# Enhanced prompting
			extend_system_message=system_prompt,
			include_tool_call_examples=True,
			**kwargs
		)
	
	def _build_navigation_prompt(
		self, 
		task: str, 
		step_number: int, 
		total_steps: int
	) -> str:
		"""Build specialized prompt for web navigation tasks."""
		
		if not self.config.use_specialized_prompts:
			return f"Complete this task: {task}"
		
		prompt = f"""You are an expert web navigation specialist. 

CURRENT TASK: {task}
PROGRESS: Step {step_number} of {total_steps}

APPROACH:
1. Take ONE precise action at a time
2. Observe the page state carefully
3. Choose the most direct path to your goal
4. If stuck, try alternative approaches
5. Call 'done' when task is complete

OPTIMIZATION RULES:
- Prefer direct element interaction over search
- Use specific selectors when available  
- Avoid unnecessary page exploration
- Focus on the immediate next action needed
- Trust your reasoning and act decisively

WEB NAVIGATION PATTERNS:
- Forms: Fill required fields, then submit
- Search: Use search box if looking for specific items
- Navigation: Click clear menu/link text when available
- Shopping: Add to cart → Proceed to checkout
- Authentication: Look for login/signin links"""

		return prompt

class PerformanceMonitor:
	"""Monitor and optimize local LLM performance."""
	
	def __init__(self):
		self.metrics = {
			'total_steps': 0,
			'successful_steps': 0,
			'failed_steps': 0,
			'recovery_attempts': 0,
			'avg_step_time': 0.0,
			'start_time': time.time()
		}
	
	def record_step(self, success: bool, duration: float):
		"""Record step performance metrics."""
		self.metrics['total_steps'] += 1
		if success:
			self.metrics['successful_steps'] += 1
		else:
			self.metrics['failed_steps'] += 1
		
		# Update average step time
		old_avg = self.metrics['avg_step_time']
		total_steps = self.metrics['total_steps']
		self.metrics['avg_step_time'] = ((old_avg * (total_steps - 1)) + duration) / total_steps
	
	def record_recovery(self):
		"""Record recovery attempt."""
		self.metrics['recovery_attempts'] += 1
	
	def get_success_rate(self) -> float:
		"""Calculate success rate."""
		if self.metrics['total_steps'] == 0:
			return 0.0
		return self.metrics['successful_steps'] / self.metrics['total_steps']
	
	def should_request_cloud_help(self) -> bool:
		"""Determine if cloud assistance is needed."""
		# Request help if success rate drops below 70% after 5+ steps
		if self.metrics['total_steps'] >= 5:
			return self.get_success_rate() < 0.7
		return False
	
	def log_performance_summary(self):
		"""Log performance summary."""
		elapsed = time.time() - self.metrics['start_time']
		success_rate = self.get_success_rate() * 100
		
		logger.info(f"[PERFORMANCE] Local LLM Performance Summary:")
		logger.info(f"  [SUCCESS] Success Rate: {success_rate:.1f}%")
		logger.info(f"  [TIME] Avg Step Time: {self.metrics['avg_step_time']:.1f}s")
		logger.info(f"  [RECOVERY] Recovery Attempts: {self.metrics['recovery_attempts']}")
		logger.info(f"  [TOTAL] Total Time: {elapsed:.1f}s")

# Usage example
async def test_optimized_local():
	"""Test the optimized local LLM configuration."""
	config = LocalLLMConfig()
	local_llm = OptimizedLocalLLM(config)
	
	# Initialize optimized client
	await local_llm.get_optimized_client()
	
	print("[READY] Enhanced Local LLM Ready for Privacy-First Web Navigation!")
	return local_llm

if __name__ == "__main__":
	asyncio.run(test_optimized_local())