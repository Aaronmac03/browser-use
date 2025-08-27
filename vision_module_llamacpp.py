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
from typing import Dict, Any, List, Optional

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
	
	def __init__(self, endpoint: str = "http://localhost:8080", model_path: Optional[str] = None):
		"""Initialize vision analyzer with llama.cpp server.
		
		Args:
			endpoint: llama.cpp server API endpoint
			model_path: Path to Moondream2 GGUF model file
		"""
		self.endpoint = endpoint
		self.model_path = model_path
		self.model_name = None  # Initialize model_name attribute
		self.manager = LlamaCppManager(endpoint=endpoint, model_path=model_path)
		self._server_available = None  # Cache availability check
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
			'recovery_time': 60,  # 1 minute recovery time
			'last_failure_time': None,
			'is_open': False
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
	
	async def _handle_circuit_breaker_failure(self):
		"""Handle circuit breaker failure logic."""
		self.circuit_breaker['consecutive_failures'] += 1
		self.circuit_breaker['last_failure_time'] = time.time()
		
		if self.circuit_breaker['consecutive_failures'] >= self.circuit_breaker['max_failures']:
			self.circuit_breaker['is_open'] = True
			print(f"[VisionAnalyzer] Circuit breaker opened after {self.circuit_breaker['consecutive_failures']} failures")
	
	async def _check_circuit_breaker(self) -> bool:
		"""Check if circuit breaker allows requests."""
		if not self.circuit_breaker['is_open']:
			return True
		
		# Check if recovery time has passed
		if (self.circuit_breaker['last_failure_time'] is not None and 
			(time.time() - self.circuit_breaker['last_failure_time']) > self.circuit_breaker['recovery_time']):
			print("[VisionAnalyzer] Circuit breaker recovery time elapsed, attempting reset")
			self.circuit_breaker['is_open'] = False
			return True
		
		return False
	
	async def _call_llama_cpp_vision(self, image_b64: str, prompt: str, timeout: float = 30.0) -> Dict[str, Any]:
		"""Call llama.cpp server vision API with error handling and performance tracking."""
		
		if not await self._check_circuit_breaker():
			return {"error": "Circuit breaker open", "performance_issue": True}
		
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
	
	async def analyze(self, screenshot_path: str, page_url: str = "", page_title: str = "", include_affordances: bool = True) -> VisionState:
		"""Analyze screenshot and return structured vision state.
		
		Args:
			screenshot_path: Path to screenshot image
			page_url: Current page URL (optional)
			page_title: Current page title (optional)
			
		Returns:
			VisionState object with analysis results
		"""
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
			print(f"[VisionAnalyzer] Image optimized: {len(image_b64)} chars")
			
			# Step 1: Basic caption and description
			caption_prompt = """Analyze this screenshot and provide:
1. A brief caption (max 50 words) describing what you see
2. List any visible text, buttons, links, or form fields
3. Describe the overall UI layout and purpose

Be concise and focus on actionable elements."""
			
			caption_result = await self._call_llama_cpp_vision(image_b64, caption_prompt, timeout=20.0)
			
			if "error" in caption_result:
				vision_state.caption = f"Analysis failed: {caption_result['error']}"
				vision_state.meta.confidence = 0.0
				vision_state.meta.processing_time = time.time() - start_time
				return vision_state
			
			# Parse basic response
			analysis_text = caption_result["content"]
			vision_state.caption = self._extract_caption(analysis_text)
			
			# Step 2: Extract elements (if affordances are requested)
			if include_affordances:
				elements_prompt = """Analyze this UI screenshot and identify interactive elements. For each clickable element, provide:
- Type (button, link, text, input field, etc.)
- Visible text or label
- Approximate position description (top-left, center, bottom-right, etc.)

Focus on elements a user can interact with."""
				
				elements_result = await self._call_llama_cpp_vision(image_b64, elements_prompt, timeout=25.0)
				
				if "error" not in elements_result:
					vision_state.elements = self._parse_elements(elements_result["content"])
					vision_state.affordances = self._elements_to_affordances(vision_state.elements)
			
			# Update metadata
			vision_state.meta.confidence = 0.8 if "error" not in caption_result else 0.3
			vision_state.meta.processing_time = time.time() - start_time
			
			print(f"[VisionAnalyzer] Analysis complete in {vision_state.meta.processing_time:.2f}s")
			return vision_state
			
		except Exception as e:
			print(f"[VisionAnalyzer] Analysis failed: {str(e)}")
			vision_state.caption = f"Analysis error: {str(e)}"
			vision_state.meta.confidence = 0.0
			vision_state.meta.processing_time = time.time() - start_time
			return vision_state
	
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
	
	async def get_performance_stats(self) -> Dict[str, Any]:
		"""Get performance statistics."""
		stats = self.performance_stats.copy()
		stats['circuit_breaker'] = self.circuit_breaker.copy()
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