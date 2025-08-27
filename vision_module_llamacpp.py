#!/usr/bin/env python3
"""
Clean Vision Module using llama.cpp server with Moondream2 GGUF
Replaces Ollama-based vision_module.py with llama.cpp server integration
Based on successful Phase 1 implementation from aug25.md.
"""

import asyncio
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

from llama_cpp_manager import LlamaCppManager


def _to_base64_jpeg(path: str, max_dim: int = 320, quality: int = 40) -> str:
	"""Convert image to optimized base64 JPEG with aggressive resizing for fast inference.
	
	Args:
		path: Path to image file
		max_dim: Maximum dimension (width or height) in pixels (reduced to 320 for speed)
		quality: JPEG quality (1-100, reduced to 40 for smaller payload)
		
	Returns:
		Base64 encoded JPEG string
	"""
	try:
		from PIL import Image
	except ImportError:
		# Fallback: raw file to base64 (slower, bigger)
		import base64, pathlib
		return base64.b64encode(pathlib.Path(path).read_bytes()).decode()

	import io, base64
	img = Image.open(path).convert("RGB")
	w, h = img.size
	
	# More aggressive resizing for faster inference
	if max(w, h) > max_dim:
		if w >= h:
			nh = int(h * (max_dim / float(w)))
			img = img.resize((max_dim, nh), Image.Resampling.LANCZOS)
		else:
			nw = int(w * (max_dim / float(h)))
			img = img.resize((nw, max_dim), Image.Resampling.LANCZOS)

	buf = io.BytesIO()
	img.save(buf, format="JPEG", quality=quality, optimize=True)
	return base64.b64encode(buf.getvalue()).decode()


# ----------------------------
# VisionState Schema (unchanged)
# ----------------------------

class VisionElement(BaseModel):
	"""Individual UI element detected by vision system."""
	role: str = Field(description="Element type: button|link|text|image|other", default="other")
	visible_text: str = Field(description="Text content visible to user", default="")
	attributes: Dict[str, str] = Field(description="HTML attributes", default_factory=dict)
	selector_hint: str = Field(description="CSS/XPath selector hint for targeting", default="")
	bbox: List[int] = Field(description="Bounding box [x,y,w,h]", default_factory=lambda: [0, 0, 0, 0])
	confidence: float = Field(description="Vision confidence score 0-1", default=0.5)


class VisionField(BaseModel):
	"""Form field detected by vision system."""
	name_hint: str = Field(description="Field name/label hint", default="")
	value_hint: str = Field(description="Current field value if visible", default="")
	bbox: List[int] = Field(description="Bounding box [x,y,w,h]", default_factory=lambda: [0, 0, 0, 0])
	editable: bool = Field(description="Whether field accepts input", default=True)


class VisionAffordance(BaseModel):
	"""Interactive affordance detected by vision system."""
	type: str = Field(description="Affordance type: button|link|tab|menu|icon", default="button")
	label: str = Field(description="Human-readable label", default="")
	selector_hint: str = Field(description="CSS/XPath selector hint", default="")
	bbox: List[int] = Field(description="Bounding box [x,y,w,h]", default_factory=lambda: [0, 0, 0, 0])


class VisionMeta(BaseModel):
	"""Page metadata from vision analysis."""
	url: str = Field(description="Current page URL", default="")
	title: str = Field(description="Page title", default="")
	scrollY: int = Field(description="Vertical scroll position", default=0)
	timestamp: str = Field(description="ISO8601 timestamp of capture", default_factory=lambda: datetime.now().isoformat())
	model_name: str = Field(description="Vision model used", default="moondream2")
	confidence: float = Field(description="Overall analysis confidence", default=0.5)
	processing_time: float = Field(description="Processing time in seconds", default=0.0)


class VisionState(BaseModel):
	"""Complete vision state of current page."""
	caption: str = Field(description="Brief description of page content", max_length=200, default="UI screenshot")
	elements: List[VisionElement] = Field(description="UI elements detected", default_factory=list)
	fields: List[VisionField] = Field(description="Form fields detected", default_factory=list)
	affordances: List[VisionAffordance] = Field(description="Interactive elements", default_factory=list)
	meta: VisionMeta = Field(description="Page metadata", default_factory=VisionMeta)


# ----------------------------
# VisionAnalyzer Class - Updated for llama.cpp server
# ----------------------------

class VisionAnalyzer:
	"""Clean vision analyzer for Browser-Use integration using llama.cpp server."""
	
	def __init__(self, endpoint: str = "http://localhost:8080", model_path: Optional[str] = None, 
				enable_cache: bool = True):
		"""Initialize vision analyzer with llama.cpp server.
		
		Args:
			endpoint: llama.cpp server API endpoint
			model_path: Path to Moondream2 GGUF model file
			enable_cache: Enable vision response caching
		"""
		self.endpoint = endpoint
		self.model_path = model_path
		self.model_name = None  # Initialize model_name attribute
		self.manager = LlamaCppManager(endpoint=endpoint, model_path=model_path)
		self._server_available = None  # Cache availability check
		
		# Initialize vision cache if enabled
		self.cache_enabled = enable_cache
		self.vision_cache = None
		if enable_cache:
			try:
				from vision_cache import VisionCache
				self.vision_cache = VisionCache()
			except ImportError:
				print("[VisionAnalyzer] Vision caching disabled - vision_cache module not available")
		self.performance_stats = {
			'total_calls': 0,
			'successful_calls': 0,
			'timeout_calls': 0,
			'avg_response_time': 0.0,
			'last_successful_time': None
		}
		self.circuit_breaker = {
			'consecutive_failures': 0,
			'max_failures': 5,  # Allow more failures before circuit breaker
			'base_recovery_time': 30,  # Base recovery time in seconds
			'max_recovery_time': 300,  # Maximum recovery time (5 minutes)
			'backoff_multiplier': 2.0,  # Exponential backoff multiplier
			'last_failure_time': None,
			'is_open': False,
			'half_open_attempts': 0,  # Track attempts in half-open state
			'max_half_open_attempts': 3  # Max attempts in half-open before full open
		}
	
	async def check_server_availability(self) -> bool:
		"""Check if llama.cpp server is running and accessible."""
		if self._server_available is not None:
			return self._server_available
			
		try:
			status = await self.manager.check_server_status()
			self._server_available = status.running and status.model_loaded
			if self._server_available:
				print(f"[VisionAnalyzer] llama.cpp server detected at {self.endpoint}")
			else:
				print(f"[VisionAnalyzer] llama.cpp server not ready at {self.endpoint}")
			return self._server_available
		except Exception as e:
			print(f"[VisionAnalyzer] Server availability check failed: {e}")
			self._server_available = False
			return False
	
	async def _reset_circuit_breaker(self):
		"""Reset circuit breaker on successful operation."""
		self.circuit_breaker['consecutive_failures'] = 0
		self.circuit_breaker['is_open'] = False
		self.circuit_breaker['last_failure_time'] = None
		self.circuit_breaker['half_open_attempts'] = 0
	
	async def _handle_circuit_breaker_failure(self):
		"""Handle circuit breaker failure logic with exponential backoff."""
		self.circuit_breaker['consecutive_failures'] += 1
		self.circuit_breaker['last_failure_time'] = time.time()
		
		if self.circuit_breaker['consecutive_failures'] >= self.circuit_breaker['max_failures']:
			self.circuit_breaker['is_open'] = True
			
			# Calculate exponential backoff recovery time
			failures = self.circuit_breaker['consecutive_failures']
			recovery_time = min(
				self.circuit_breaker['base_recovery_time'] * (self.circuit_breaker['backoff_multiplier'] ** (failures - self.circuit_breaker['max_failures'])),
				self.circuit_breaker['max_recovery_time']
			)
			
			print(f"[VisionAnalyzer] Circuit breaker opened after {failures} failures (recovery in {recovery_time:.1f}s)")
	
	async def _check_circuit_breaker(self) -> Tuple[bool, str]:
		"""Check if circuit breaker allows requests with exponential backoff.
		
		Returns:
			Tuple of (allow_request, state_description)
		"""
		if not self.circuit_breaker['is_open']:
			return True, "closed"
		
		if self.circuit_breaker['last_failure_time'] is None:
			return False, "open"
		
		# Calculate exponential backoff recovery time
		failures = self.circuit_breaker['consecutive_failures']
		recovery_time = min(
			self.circuit_breaker['base_recovery_time'] * (self.circuit_breaker['backoff_multiplier'] ** max(0, failures - self.circuit_breaker['max_failures'])),
			self.circuit_breaker['max_recovery_time']
		)
		
		time_since_failure = time.time() - self.circuit_breaker['last_failure_time']
		
		if time_since_failure >= recovery_time:
			# Enter half-open state - allow limited attempts
			if self.circuit_breaker['half_open_attempts'] < self.circuit_breaker['max_half_open_attempts']:
				self.circuit_breaker['half_open_attempts'] += 1
				print(f"[VisionAnalyzer] Circuit breaker half-open: attempt {self.circuit_breaker['half_open_attempts']}/{self.circuit_breaker['max_half_open_attempts']}")
				return True, "half_open"
			else:
				# Too many half-open failures, back to full open with increased backoff
				self.circuit_breaker['half_open_attempts'] = 0
				self.circuit_breaker['last_failure_time'] = time.time()
				print(f"[VisionAnalyzer] Circuit breaker back to open state - recovery in {recovery_time * self.circuit_breaker['backoff_multiplier']:.1f}s")
				return False, "open"
		
		remaining_time = recovery_time - time_since_failure
		return False, f"open (recovery in {remaining_time:.1f}s)"
	
	async def _call_llama_cpp_vision(self, image_b64: str, prompt: str, timeout: float = 30.0) -> Dict[str, Any]:
		"""Call llama.cpp server vision API with error handling and performance tracking."""
		
		allow_request, breaker_state = await self._check_circuit_breaker()
		if not allow_request:
			return {"error": f"Circuit breaker {breaker_state}", "performance_issue": True}
		
		self.performance_stats['total_calls'] += 1
		start_time = time.time()
		
		try:
			timeout_config = httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=10.0)
			
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				payload = {
					"messages": [{
						"role": "user",
						"content": [
							{"type": "text", "text": prompt},
							{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
						]
					}],
					"max_tokens": 1024,
					"temperature": 0.1,
					"stream": False
				}
				
				response = await client.post(f"{self.endpoint}/v1/chat/completions", json=payload)
				response.raise_for_status()
				
				result = response.json()
				
				if "choices" not in result or not result["choices"]:
					return {"error": "No response choices from server"}
				
				content = result["choices"][0]["message"]["content"]
				
				# Success tracking
				elapsed = time.time() - start_time
				self.performance_stats['successful_calls'] += 1
				self.performance_stats['last_successful_time'] = time.time()
				
				# Update rolling average
				total_successful = self.performance_stats['successful_calls']
				old_avg = self.performance_stats['avg_response_time']
				self.performance_stats['avg_response_time'] = ((old_avg * (total_successful - 1)) + elapsed) / total_successful
				
				await self._reset_circuit_breaker()
				
				print(f"[VisionAnalyzer] Vision call successful in {elapsed:.2f}s")
				return {"content": content, "response_time": elapsed}
				
		except asyncio.TimeoutError:
			print(f"[VisionAnalyzer] Vision call timed out after {timeout}s")
			self.performance_stats['timeout_calls'] += 1
			await self._handle_circuit_breaker_failure()
			return {"error": "Request timed out", "timeout": True}
			
		except httpx.HTTPStatusError as e:
			print(f"[VisionAnalyzer] HTTP error {e.response.status_code}: {e.response.text}")
			await self._handle_circuit_breaker_failure()
			return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
			
		except Exception as e:
			print(f"[VisionAnalyzer] Vision call failed: {str(e)}")
			await self._handle_circuit_breaker_failure()
			return {"error": str(e)}
	
	async def analyze_with_retry(self, screenshot_path: str, page_url: str = "", 
								page_title: str = "", include_affordances: bool = True,
								max_retries: int = 3) -> VisionState:
		"""Analyze screenshot with retry and parameter variation."""
		
		# Retry parameters - progressive fallback
		retry_configs = [
			{'timeout': 30.0, 'max_tokens': 1024, 'temperature': 0.1, 'prompt_type': 'detailed'},
			{'timeout': 45.0, 'max_tokens': 512, 'temperature': 0.2, 'prompt_type': 'simplified'},
			{'timeout': 60.0, 'max_tokens': 256, 'temperature': 0.3, 'prompt_type': 'basic'}
		]
		
		last_error = None
		
		for attempt in range(min(max_retries, len(retry_configs))):
			config = retry_configs[attempt]
			
			if attempt > 0:
				print(f"[VisionAnalyzer] Retry attempt {attempt + 1}/{max_retries} with {config['prompt_type']} config")
				# Small delay between retries
				await asyncio.sleep(2 ** attempt)  # Exponential delay
			
			try:
				result = await self._analyze_with_config(
					screenshot_path, page_url, page_title, include_affordances, config
				)
				
				# Check if result is acceptable
				if result.meta.confidence > 0.3:  # Minimum acceptable confidence
					if attempt > 0:
						print(f"[VisionAnalyzer] Retry successful on attempt {attempt + 1}")
					
					# Cache successful result if caching is enabled
					if self.vision_cache is not None and result.meta.confidence > 0.5:
						try:
							prompt = self.build_vision_prompt()
							model_variant = self.model_name or "default"
							result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
							
							await self.vision_cache.put(
								screenshot_path, prompt, result_dict,
								result.meta.confidence, result.meta.processing_time, model_variant
							)
						except Exception as e:
							print(f"[VisionAnalyzer] Failed to cache retry result: {e}")
					
					return result
				else:
					last_error = f"Low confidence result: {result.meta.confidence}"
					
			except Exception as e:
				last_error = str(e)
				print(f"[VisionAnalyzer] Attempt {attempt + 1} failed: {e}")
		
		# If all retries failed, return minimal result
		print(f"[VisionAnalyzer] All retry attempts failed, last error: {last_error}")
		vision_state = VisionState()
		vision_state.meta.timestamp = datetime.now().isoformat()
		vision_state.meta.model_name = "moondream2-gguf"
		vision_state.meta.url = page_url
		vision_state.meta.title = page_title
		vision_state.caption = f"Vision analysis failed after {max_retries} attempts: {last_error}"
		vision_state.meta.confidence = 0.0
		
		return vision_state
	
	async def _analyze_with_config(self, screenshot_path: str, page_url: str, 
								 page_title: str, include_affordances: bool,
								 config: Dict[str, Any]) -> VisionState:
		"""Internal analyze method with specific configuration."""
		start_time = time.time()
		
		# Initialize basic vision state
		vision_state = VisionState()
		vision_state.meta.timestamp = datetime.now().isoformat()
		vision_state.meta.model_name = "moondream2-gguf"
		vision_state.meta.url = page_url
		vision_state.meta.title = page_title
		
		# Ensure server is available
		if not await self.check_server_availability():
			if not await self.manager.ensure_server_running():
				vision_state.caption = "Vision analysis failed: llama.cpp server not available"
				vision_state.meta.confidence = 0.0
				return vision_state
		
		try:
			# Convert image to base64
			image_b64 = _to_base64_jpeg(screenshot_path)
			
			# Select prompt based on config
			if config.get('prompt_type') == 'basic':
				prompt = "Describe what you see in this image briefly."
			elif config.get('prompt_type') == 'simplified':
				prompt = """Analyze this webpage screenshot. Provide:
1. Brief description of the page
2. List main interactive elements (buttons, links)
3. Any visible text or prices"""
			else:  # detailed
				prompt = self.build_vision_prompt()
			
			# Call vision API with config parameters
			result = await self._call_llama_cpp_vision_with_config(image_b64, prompt, config)
			
			if "error" in result:
				raise Exception(f"Vision call failed: {result['error']}")
			
			# Parse response
			analysis_text = result["content"]
			vision_state.caption = self._extract_caption(analysis_text)
			
			# Extract elements only for detailed analysis
			if config.get('prompt_type') == 'detailed' and include_affordances:
				elements_prompt = """Identify clickable elements in this UI. List each element with its type (button/link) and text."""
				
				elements_result = await self._call_llama_cpp_vision_with_config(image_b64, elements_prompt, config)
				
				if "error" not in elements_result:
					vision_state.elements = self._parse_elements(elements_result["content"])
					vision_state.affordances = self._elements_to_affordances(vision_state.elements)
			
			# Set confidence based on config quality and content richness
			base_confidence = 0.8 if config.get('prompt_type') == 'detailed' else 0.6
			content_bonus = min(0.2, len(vision_state.caption) / 200.0)
			vision_state.meta.confidence = min(1.0, base_confidence + content_bonus)
			
			vision_state.meta.processing_time = time.time() - start_time
			
			return vision_state
			
		except Exception as e:
			vision_state.caption = f"Analysis error with {config.get('prompt_type', 'default')} config: {str(e)}"
			vision_state.meta.confidence = 0.0
			vision_state.meta.processing_time = time.time() - start_time
			raise
	
	async def _call_llama_cpp_vision_with_config(self, image_b64: str, prompt: str, 
											   config: Dict[str, Any]) -> Dict[str, Any]:
		"""Call vision API with specific configuration parameters."""
		allow_request, breaker_state = await self._check_circuit_breaker()
		if not allow_request:
			return {"error": f"Circuit breaker {breaker_state}", "performance_issue": True}
		
		self.performance_stats['total_calls'] += 1
		start_time = time.time()
		
		timeout = config.get('timeout', 30.0)
		max_tokens = config.get('max_tokens', 1024)
		temperature = config.get('temperature', 0.1)
		
		try:
			timeout_config = httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=10.0)
			
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				payload = {
					"messages": [{
						"role": "user",
						"content": [
							{"type": "text", "text": prompt},
							{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
						]
					}],
					"max_tokens": max_tokens,
					"temperature": temperature,
					"stream": False
				}
				
				response = await client.post(f"{self.endpoint}/v1/chat/completions", json=payload)
				response.raise_for_status()
				
				result = response.json()
				
				if "choices" not in result or not result["choices"]:
					return {"error": "No response choices from server"}
				
				content = result["choices"][0]["message"]["content"]
				
				# Success tracking
				elapsed = time.time() - start_time
				self.performance_stats['successful_calls'] += 1
				self.performance_stats['last_successful_time'] = time.time()
				
				# Update rolling average
				total_successful = self.performance_stats['successful_calls']
				old_avg = self.performance_stats['avg_response_time']
				self.performance_stats['avg_response_time'] = ((old_avg * (total_successful - 1)) + elapsed) / total_successful
				
				await self._reset_circuit_breaker()
				
				return {"content": content, "response_time": elapsed}
				
		except asyncio.TimeoutError:
			self.performance_stats['timeout_calls'] += 1
			await self._handle_circuit_breaker_failure()
			return {"error": "Request timed out", "timeout": True}
			
		except httpx.HTTPStatusError as e:
			await self._handle_circuit_breaker_failure()
			return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
			
		except Exception as e:
			await self._handle_circuit_breaker_failure()
			return {"error": str(e)}
	
	async def analyze(self, screenshot_path: str, page_url: str = "", page_title: str = "", include_affordances: bool = True) -> VisionState:
		"""Analyze screenshot and return structured vision state with built-in retry.
		
		Args:
			screenshot_path: Path to screenshot image
			page_url: Current page URL (optional)
			page_title: Current page title (optional)
			
		Returns:
			VisionState object with analysis results
		"""
		# Try cache first if enabled
		if self.vision_cache is not None:
			prompt = self.build_vision_prompt()
			model_variant = self.model_name or "default"
			
			cached_result = await self.vision_cache.get(screenshot_path, prompt, model_variant)
			if cached_result is not None:
				print(f"[VisionAnalyzer] Cache hit (similarity: {cached_result.get('cache_similarity', 1.0):.2f})")
				
				# Update metadata with current context
				if 'meta' in cached_result:
					cached_result['meta']['url'] = page_url
					cached_result['meta']['title'] = page_title
					cached_result['meta']['timestamp'] = datetime.now().isoformat()
				
				try:
					return VisionState(**cached_result)
				except Exception as e:
					print(f"[VisionAnalyzer] Failed to reconstruct from cache: {e}")
					# Fall through to fresh analysis
		
		# Use retry analysis for fresh analysis
		return await self.analyze_with_retry(screenshot_path, page_url, page_title, include_affordances)
	
	def _extract_caption(self, analysis_text: str) -> str:
		"""Extract concise caption from analysis text."""
		lines = analysis_text.strip().split('\n')
		for line in lines:
			line = line.strip()
			if line and not line.startswith('1.') and not line.startswith('-') and len(line) > 10:
				# Take first substantial line as caption, limit length
				return line[:200] if len(line) <= 200 else line[:197] + "..."
		
		# Fallback: use first 200 chars of entire response
		return analysis_text[:200] if len(analysis_text) <= 200 else analysis_text[:197] + "..."
	
	def _parse_elements(self, elements_text: str) -> List[VisionElement]:
		"""Parse elements from vision analysis text."""
		elements = []
		lines = elements_text.strip().split('\n')
		
		current_element = None
		for line in lines:
			line = line.strip()
			if not line:
				continue
			
			# Look for element indicators
			if any(keyword in line.lower() for keyword in ['button', 'link', 'input', 'text', 'field']):
				if current_element:
					elements.append(current_element)
				
				# Extract element type
				element_type = "other"
				if "button" in line.lower():
					element_type = "button"
				elif "link" in line.lower():
					element_type = "link"
				elif "input" in line.lower() or "field" in line.lower():
					element_type = "text"
				
				# Extract visible text (basic heuristic)
				visible_text = ""
				if ":" in line:
					parts = line.split(":", 1)
					if len(parts) > 1:
						visible_text = parts[1].strip().strip('"').strip("'")
				
				current_element = VisionElement(
					role=element_type,
					visible_text=visible_text,
					confidence=0.6
				)
		
		# Add last element
		if current_element:
			elements.append(current_element)
		
		return elements
	
	def _elements_to_affordances(self, elements: List[VisionElement]) -> List[VisionAffordance]:
		"""Convert elements to affordances for interaction."""
		affordances = []
		
		for element in elements:
			if element.role in ['button', 'link']:
				affordances.append(VisionAffordance(
					type=element.role,
					label=element.visible_text or f"{element.role}",
					bbox=element.bbox
				))
		
		return affordances
	
	def build_vision_prompt(self) -> str:
		"""Build the richer vision analysis prompt prioritizing key elements."""
		return """Analyze this webpage screenshot and identify up to 8 key interactive elements. Focus on the most important elements only.

CRITICAL JSON FORMAT RULES:
1. Return ONLY a single JSON object (not array)
2. NO trailing commas anywhere
3. NO ellipses (...) or incomplete elements
4. ALL strings must be properly quoted
5. ALL arrays and objects must be complete

Required JSON structure:
{
  "caption": "brief page description",
  "elements": [
    {
      "role": "button",
      "visible_text": "exact text shown",
      "attributes": {},
      "selector_hint": "button",
      "bbox": [0, 0, 100, 50],
      "confidence": 0.8
    }
  ],
  "fields": [],
  "affordances": []
}

PRIORITY ELEMENTS (find these first):
- Search inputs and search buttons
- Price displays ($X.XX, pricing info)
- Cart/checkout buttons ("Add to Cart", "Checkout")
- Zip code/location fields
- Cookie/banner buttons ("Accept", "Close", "X")
- Primary navigation buttons

IMPORTANT: 
- If you see fewer than 8 elements, that's fine - quality over quantity
- Every element must be complete with all required fields
- Use simple, clear text for visible_text field"""

	async def resolve_moondream_tag(self) -> str:
		"""Resolve Moondream2 model name for llama.cpp server."""
		try:
			print(f"[VisionAnalyzer] Resolving model info from {self.endpoint}")
			async with httpx.AsyncClient(timeout=10.0) as client:
				response = await client.get(f"{self.endpoint}/v1/models")
				if response.status_code == 200:
					data = response.json()
					models = data.get('data', [])
					if models:
						model_name = models[0].get('id', 'moondream2-gguf')
						print(f"[VisionAnalyzer] Found model: {model_name}")
						return model_name
					else:
						print(f"[VisionAnalyzer] No models found, using default")
						return "moondream2-gguf"
				else:
					print(f"[VisionAnalyzer] Failed to get models: HTTP {response.status_code}")
					return "moondream2-gguf"
		except Exception as e:
			print(f"[VisionAnalyzer] Error resolving model: {type(e).__name__}: {e}")
			return "moondream2-gguf"
	
	async def warm_up_model(self, timeout: float = 30.0) -> Dict[str, Any]:
		"""Warm up the vision model with optimized test calls.
		
		Args:
			timeout: Maximum time to spend on warm-up
			
		Returns:
			Dict with warm-up results and timing
		"""
		print(f"[VisionAnalyzer] Starting model warm-up (timeout: {timeout}s)")
		start_time = time.time()
		
		# Ensure server is available
		if not await self.check_server_availability():
			if not await self.manager.ensure_server_running():
				return {
					'success': False,
					'error': 'Server not available',
					'elapsed': time.time() - start_time
				}
		
		# Resolve model name if not set
		if not self.model_name:
			self.model_name = await self.resolve_moondream_tag()
		
		# Create minimal test image (1x1 white pixel PNG)
		tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
		
		# Progressive warm-up with increasing complexity
		warm_up_prompts = [
			"What color is this image?",  # Simple question
			"Describe what you see.",      # Medium complexity  
			"List interactive elements."   # Full complexity
		]
		
		successful_calls = 0
		total_attempts = len(warm_up_prompts)
		
		try:
			for i, prompt in enumerate(warm_up_prompts):
				call_timeout = min(10.0, (timeout - (time.time() - start_time)) / (total_attempts - i))
				if call_timeout <= 0:
					break
					
				print(f"[VisionAnalyzer] Warm-up call {i+1}/{total_attempts}...")
				
				try:
					result = await asyncio.wait_for(
						self._call_llama_cpp_vision(tiny_png_b64, prompt, timeout=call_timeout),
						timeout=call_timeout + 2.0
					)
					
					if "error" not in result:
						successful_calls += 1
						print(f"[VisionAnalyzer] Warm-up call {i+1} successful ({result.get('response_time', 0):.2f}s)")
					else:
						print(f"[VisionAnalyzer] Warm-up call {i+1} failed: {result['error']}")
				
				except asyncio.TimeoutError:
					print(f"[VisionAnalyzer] Warm-up call {i+1} timed out")
					break
				except Exception as e:
					print(f"[VisionAnalyzer] Warm-up call {i+1} exception: {e}")
		
		except Exception as e:
			print(f"[VisionAnalyzer] Warm-up process failed: {e}")
		
		elapsed = time.time() - start_time
		success_rate = successful_calls / total_attempts
		
		# Reset circuit breaker on successful warm-up
		if success_rate >= 0.5:  # At least half the warm-up calls succeeded
			await self._reset_circuit_breaker()
			print(f"[VisionAnalyzer] Model warm-up successful ({success_rate:.1%} success, {elapsed:.1f}s)")
		else:
			print(f"[VisionAnalyzer] Model warm-up completed with issues ({success_rate:.1%} success, {elapsed:.1f}s)")
		
		return {
			'success': success_rate >= 0.5,
			'success_rate': success_rate,
			'successful_calls': successful_calls,
			'total_attempts': total_attempts,
			'elapsed': elapsed,
			'model_name': self.model_name
		}
	
	async def get_performance_stats(self) -> Dict[str, Any]:
		"""Get performance statistics."""
		stats = self.performance_stats.copy()
		stats['circuit_breaker'] = self.circuit_breaker.copy()
		if self.vision_cache is not None:
			cache_stats = await self.vision_cache.get_stats()
			stats['cache'] = cache_stats
		return stats


async def test_vision_analyzer():
	"""Test the vision analyzer with a sample image."""
	analyzer = VisionAnalyzer()
	
	# Check if server is available
	if not await analyzer.check_server_availability():
		print("Starting llama.cpp server...")
		if not await analyzer.manager.ensure_server_running():
			print("Failed to start server")
			return
	
	# Test with a simple image (you would provide a real screenshot path)
	print("Testing vision capability...")
	result = await analyzer.manager.test_vision_capability()
	
	if result.get("success"):
		print(f"✓ Vision test successful: {result['description']}")
	else:
		print(f"✗ Vision test failed: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
	asyncio.run(test_vision_analyzer())