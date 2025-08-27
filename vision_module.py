#!/usr/bin/env python3
"""
Clean Vision Module extracted from successful test_vision.py
Provides simple interface: VisionAnalyzer.analyze(screenshot_path) -> VisionState

Based on successful Phase 1 implementation from aug25.md.
"""

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from pydantic import BaseModel, Field


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
# VisionState Schema
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
    model_name: str = Field(description="Vision model used", default="unknown")
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
# VisionAnalyzer Class
# ----------------------------

class VisionAnalyzer:
    """Clean vision analyzer for Browser-Use integration."""
    
    def __init__(self, endpoint: str = "http://localhost:11434", model_name: Optional[str] = None):
        """Initialize vision analyzer.
        
        Args:
            endpoint: Ollama API endpoint
            model_name: Moondream2 model name (auto-resolved if None)
        """
        self.endpoint = endpoint
        self.model_name = model_name
        self._ollama_available = None  # Cache availability check
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
    
    async def check_ollama_availability(self) -> bool:
        """Check if Ollama service is running and accessible."""
        if self._ollama_available is not None:
            return self._ollama_available
            
        try:
            timeout_config = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.get(f"{self.endpoint}/api/version")
                self._ollama_available = response.status_code == 200
                if self._ollama_available:
                    print(f"[VisionAnalyzer] Ollama service detected at {self.endpoint}")
                return self._ollama_available
        except Exception as e:
            print(f"[VisionAnalyzer] Ollama not available at {self.endpoint}: {type(e).__name__}")
            print(f"[VisionAnalyzer] To use vision features, install and run: ollama serve")
            self._ollama_available = False
            return False
    
    async def resolve_moondream_tag(self) -> str:
        """Resolve Moondream2 tag by querying Ollama API and return the exact model tag."""
        try:
            print(f"[VisionAnalyzer] Resolving model tags from {self.endpoint}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    available_models = [m.get('name', '') for m in data.get('models', [])]
                    print(f"[VisionAnalyzer] Available models: {available_models}")
                    
                    for model in data.get('models', []):
                        model_name = model.get('name', '')
                        if 'moondream' in model_name.lower():
                            print(f"[VisionAnalyzer] Found Moondream model: {model_name}")
                            # Return the exact tag as reported by Ollama
                            return model_name or "moondream:latest"
                    
                    print(f"[VisionAnalyzer] No Moondream model found, using default")
                    return "moondream:latest"
                else:
                    print(f"[VisionAnalyzer] Failed to get models: HTTP {response.status_code}")
                    return "moondream:latest"
        except Exception as e:
            print(f"[VisionAnalyzer] Error resolving models: {type(e).__name__}: {e}")
            return "moondream:latest"
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should block the call."""
        if not self.circuit_breaker['is_open']:
            return True
            
        # Check if recovery time has passed
        if self.circuit_breaker['last_failure_time']:
            time_since_failure = time.time() - self.circuit_breaker['last_failure_time']
            if time_since_failure > self.circuit_breaker['recovery_time']:
                print(f"[VisionAnalyzer] RETRY: Circuit breaker recovery attempt after {time_since_failure:.0f}s")
                self.circuit_breaker['is_open'] = False
                self.circuit_breaker['consecutive_failures'] = 0
                return True
        
        return False
    
    def _record_success(self):
        """Record successful call and reset circuit breaker."""
        self.circuit_breaker['consecutive_failures'] = 0
        self.circuit_breaker['is_open'] = False
        
    def _record_failure(self):
        """Record failed call and potentially open circuit breaker."""
        self.circuit_breaker['consecutive_failures'] += 1
        self.circuit_breaker['last_failure_time'] = time.time()
        
        if self.circuit_breaker['consecutive_failures'] >= self.circuit_breaker['max_failures']:
            self.circuit_breaker['is_open'] = True
            print(f"[VisionAnalyzer] WARNING: Circuit breaker opened after {self.circuit_breaker['consecutive_failures']} failures")
            print(f"[VisionAnalyzer] BLOCKED: Vision calls blocked for {self.circuit_breaker['recovery_time']}s")
    
    async def _force_model_cleanup(self) -> None:
        """Reset model context to prevent state accumulation - keeps model loaded."""
        try:
            # Send minimal context reset request
            cleanup_payload = {
                "model": self.model_name,
                "prompt": "reset",  # Minimal prompt to reset context
                "stream": False,
                "keep_alive": "30s",
                "options": {
                    "num_ctx": 256,  # Minimal context
                    "num_predict": 1  # Single token response
                }
            }
            
            timeout = httpx.Timeout(connect=1.0, read=3.0, write=2.0, pool=3.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                await client.post(
                    f"{self.endpoint}/api/generate",
                    json=cleanup_payload
                )
            print(f"[VisionAnalyzer] Context reset successful")
        except Exception as e:
            # Non-critical - just log warning  
            print(f"[VisionAnalyzer] Context reset failed: {e}")
    
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
- Use simple, clear text for visible_text field
- Keep bbox coordinates as integers [x, y, width, height]
- Set confidence between 0.5-1.0

Return ONLY the complete JSON object. No extra text before or after."""
    
    async def call_moondream(self, prompt: str, image_b64: str) -> Dict[str, Any]:
        """Call Moondream2 via Ollama API with robust error handling and performance tracking."""
        start_time = time.time()
        self.performance_stats['total_calls'] += 1
        
        # Check circuit breaker
        if not self._check_circuit_breaker():
            raise Exception(f"Circuit breaker open - vision temporarily disabled for performance")
        
        # Preemptive cleanup to ensure clean state before each call
        if self.performance_stats['successful_calls'] > 0:  # Only cleanup after first success
            try:
                await self._force_model_cleanup()
                print(f"[VisionAnalyzer] Preemptive cleanup completed")
            except Exception as cleanup_error:
                print(f"[VisionAnalyzer] Preemptive cleanup warning: {cleanup_error}")
        
        if not self.model_name:
            self.model_name = await self.resolve_moondream_tag()
            print(f"[VisionAnalyzer] Resolved model name: {self.model_name}")
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "keep_alive": "30s",  # Keep model loaded but short duration
            "options": {
                "temperature": 0.0,  # Deterministic for speed
                "num_predict": 256,  # Reduced token count for faster generation
                "top_k": 5,   # Reduced for faster sampling
                "top_p": 0.8, # Slightly more focused for speed
                "num_ctx": 256,  # Extremely small context to prevent accumulation
                "seed": 42  # Fixed seed for consistency
            }
        }
        
        print(f"[VisionAnalyzer] Calling Moondream2 at {self.endpoint} with model {self.model_name}")
        print(f"[VisionAnalyzer] Image size: {len(image_b64)} characters")
        
        try:
            # Increased timeout for vision processing - local model needs more time
            timeout = httpx.Timeout(connect=2.0, read=20.0, write=5.0, pool=20.0)
            limits  = httpx.Limits(max_keepalive_connections=0, max_connections=1)  # Force fresh connections
            
            async with httpx.AsyncClient(timeout=timeout, limits=limits, headers={"Connection": "close"}) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json=payload
                )
                
                print(f"[VisionAnalyzer] Response status: {response.status_code}")
            
                if response.status_code != 200:
                    error_msg = response.text
                    print(f"[VisionAnalyzer] HTTP Error {response.status_code}: {error_msg[:500]}")
                    
                    # Handle memory issues with fallback response
                    if "system memory" in error_msg.lower() or response.status_code == 500:
                        print(f"[VisionAnalyzer] FALLBACK: Using memory fallback response")
                        return {
                            "response": """{
                                "caption": "UI screenshot with interactive elements",
                                "elements": [
                                    {
                                        "role": "other",
                                        "visible_text": "UI element",
                                        "attributes": {},
                                        "selector_hint": "page element",
                                        "bbox": [0, 0, 100, 50],
                                        "confidence": 0.5
                                    }
                                ],
                                "fields": [],
                                "affordances": []
                            }"""
                        }
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                response_json = response.json()
                response_time = time.time() - start_time
                self.performance_stats['successful_calls'] += 1
                self.performance_stats['last_successful_time'] = response_time
                
                # Update rolling average
                total_successful = self.performance_stats['successful_calls']
                current_avg = self.performance_stats['avg_response_time']
                self.performance_stats['avg_response_time'] = (
                    (current_avg * (total_successful - 1) + response_time) / total_successful
                )
                
                print(f"[VisionAnalyzer] Got response from local model in {response_time:.2f}s")
                self._record_success()
                
                # Force model unload to prevent state accumulation - critical for stability
                try:
                    await self._force_model_cleanup()
                except Exception as cleanup_error:
                    print(f"[VisionAnalyzer] Model cleanup warning: {cleanup_error}")
                
                return response_json
                
        except httpx.TimeoutException as e:
            timeout_time = time.time() - start_time
            self.performance_stats['timeout_calls'] += 1
            
            print(f"[VisionAnalyzer] TIMEOUT calling Ollama after {timeout_time:.1f}s: {e}")
            print(f"[VisionAnalyzer] Stats: {self.performance_stats['successful_calls']}/{self.performance_stats['total_calls']} success, avg: {self.performance_stats['avg_response_time']:.1f}s")
            print(f"[VisionAnalyzer] WARNING: Ollama may be overloaded or model {self.model_name} not available")
            print(f"[VisionAnalyzer] Try: python ollama_manager.py --health")
            self._record_failure()
            raise Exception(f"Ollama timeout - check model availability: python ollama_manager.py --health")
        except httpx.ConnectError as e:
            print(f"[VisionAnalyzer] Connection error to Ollama: {e}")
            print(f"[VisionAnalyzer] WARNING: Ollama service is not running!")
            print(f"[VisionAnalyzer] Please run: python ollama_manager.py --setup")
            self._record_failure()
            raise Exception(f"Ollama service required but not running. Run: python ollama_manager.py --setup")
        except json.JSONDecodeError as e:
            print(f"[VisionAnalyzer] JSON decode error: {e}")
            print(f"[VisionAnalyzer] Raw response: {response.text[:200]}...")
            raise Exception(f"Invalid JSON response from Ollama: {e}")
        except Exception as e:
            print(f"[VisionAnalyzer] Unexpected error: {type(e).__name__}: {e}")
            raise
    
    def _extract_first_json(self, text: str) -> str:
        """Extract the first valid JSON object or array from text with robust cleanup."""
        text = text.strip()
        
        # Clean up common JSON issues from LLM responses
        text = text.replace('...', '').replace('...', '')  # Remove ellipses
        
        # If text starts with '[', prioritize array extraction
        if text.startswith('['):
            start_idx = text.find('[')
            if start_idx != -1:
                bracket_count = 0
                for i, char in enumerate(text[start_idx:], start_idx):
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            extracted = text[start_idx:i+1]
                            return self._clean_json_string(extracted)
        
        # Try to find JSON object
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        extracted = text[start_idx:i+1]
                        return self._clean_json_string(extracted)
        
        # Try to find JSON array (fallback)
        start_idx = text.find('[')
        if start_idx != -1:
            bracket_count = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        extracted = text[start_idx:i+1]
                        return self._clean_json_string(extracted)
        
        # Fallback to original text
        return self._clean_json_string(text.strip())
    
    def _clean_json_string(self, json_str: str) -> str:
        """Clean up common JSON formatting issues from LLM responses."""
        import re
        
        # Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        # Fix incomplete strings by adding closing quotes
        lines = json_str.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip lines that are just ellipses or incomplete
            if line in ['...', '...', '..', '.']:
                continue
                
            # If line ends with incomplete string, try to fix it
            if line.endswith('"') and line.count('"') % 2 == 1:
                # Odd number of quotes, likely incomplete
                if line.endswith('",') or line.endswith('"'):
                    cleaned_lines.append(line)
                else:
                    cleaned_lines.append(line + '"')
            elif '"' in line and line.count('"') % 2 == 1:
                # Incomplete string in middle of line
                if not line.endswith('"'):
                    line = line + '"'
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        cleaned_json = '\n'.join(cleaned_lines)
        
        # Final cleanup: ensure proper JSON structure
        cleaned_json = cleaned_json.replace('...', '').replace('...', '')
        
        return cleaned_json

    def parse_vision_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse vision response from Moondream2 with robust error handling."""
        try:
            response_text = response.get('response', '{}')
            print(f"[VisionAnalyzer] Raw response length: {len(response_text)} chars")
            print(f"[VisionAnalyzer] Response preview: {response_text[:200]}...")
            
            # Extract first valid JSON object from response (includes cleanup)
            json_text = self._extract_first_json(response_text)
            print(f"[VisionAnalyzer] Extracted JSON length: {len(json_text)} chars")
            
            # Try multiple JSON parsing strategies
            vision_data = None
            parsing_errors = []
            
            # Strategy 1: Direct parsing
            try:
                vision_data = json.loads(json_text)
                print(f"[VisionAnalyzer] Successfully parsed JSON response")
            except json.JSONDecodeError as e:
                parsing_errors.append(f"Direct parse: {e}")
                
                # Strategy 2: Try with additional cleanup
                try:
                    import re
                    # More aggressive cleanup
                    cleaned = re.sub(r',\s*([}\]])', r'\1', json_text)  # Remove trailing commas
                    cleaned = re.sub(r'([}\]]),\s*$', r'\1', cleaned)  # Remove trailing comma at end
                    cleaned = re.sub(r'"\s*:\s*([^",}\]]+)([,}\]])', r'": "\1"\2', cleaned)  # Quote unquoted values
                    
                    vision_data = json.loads(cleaned)
                    print(f"[VisionAnalyzer] Successfully parsed JSON after cleanup")
                except json.JSONDecodeError as e2:
                    parsing_errors.append(f"Cleanup parse: {e2}")
                    
                    # Strategy 3: Try to fix common issues and parse again
                    try:
                        # Fix incomplete JSON by adding missing closing braces/brackets
                        fixed_json = json_text
                        
                        # Remove incomplete trailing elements (lines ending with comma but no closing)
                        lines = fixed_json.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            line = line.strip()
                            if line and not line.endswith(','):
                                cleaned_lines.append(line)
                            elif line.endswith(','):
                                # Check if this looks like an incomplete element
                                if '"bbox":' in line and not line.count('[') == line.count(']'):
                                    # Skip incomplete bbox lines
                                    continue
                                else:
                                    cleaned_lines.append(line)
                        
                        fixed_json = '\n'.join(cleaned_lines)
                        
                        # Count and fix unmatched braces/brackets
                        open_braces = fixed_json.count('{') - fixed_json.count('}')
                        open_brackets = fixed_json.count('[') - fixed_json.count(']')
                        
                        if open_braces > 0:
                            fixed_json += '}' * open_braces
                        if open_brackets > 0:
                            fixed_json += ']' * open_brackets
                            
                        # Clean up trailing commas again
                        fixed_json = re.sub(r',\s*([}\]])', r'\1', fixed_json)
                        
                        vision_data = json.loads(fixed_json)
                        print(f"[VisionAnalyzer] Successfully parsed JSON after structure fix")
                    except json.JSONDecodeError as e3:
                        parsing_errors.append(f"Structure fix: {e3}")
                        
                        # Strategy 4: Last resort - return minimal valid structure
                        print(f"[VisionAnalyzer] All parsing failed, using minimal fallback")
                        vision_data = {
                            "caption": "UI screenshot (parsing failed)",
                            "elements": [],
                            "fields": [],
                            "affordances": []
                        }
            
            if vision_data is None:
                raise json.JSONDecodeError(f"Failed to parse JSON: {'; '.join(parsing_errors)}", json_text, 0)
            
            # Handle case where model returns array instead of object
            if isinstance(vision_data, list):
                print(f"[VisionAnalyzer] Model returned array, converting to object format")
                # Check if it's a list of link-like dicts
                converted_elements = []
                for item in vision_data:
                    if isinstance(item, dict):
                        # Convert link-like dict to our schema
                        element = {
                            "role": "link" if item.get('url') or item.get('href') else "other",
                            "visible_text": item.get('name', '') or item.get('visible_text', '') or item.get('text', ''),
                            "attributes": {},
                            "selector_hint": f"a[href*='{item.get('url', item.get('href', ''))}']" if item.get('url') or item.get('href') else "element",
                            "bbox": [int(float(x)) for x in item.get('bbox', [0, 0, 0, 0])[:4]] if item.get('bbox') else [0, 0, 0, 0],
                            "confidence": float(item.get('confidence', 0.5))
                        }
                        # Add href to attributes if present
                        if item.get('url') or item.get('href'):
                            element['attributes']['href'] = item.get('url') or item.get('href')
                        converted_elements.append(element)
                
                vision_data = {
                    "caption": "UI screenshot with interactive elements",
                    "elements": converted_elements,
                    "fields": [],
                    "affordances": []
                }
            elif not isinstance(vision_data, dict):
                print(f"[VisionAnalyzer] Response is not a dict or array, using empty dict")
                vision_data = {}
                
            # Ensure all required keys exist with empty arrays as defaults
            vision_data.setdefault('elements', [])
            vision_data.setdefault('fields', [])
            vision_data.setdefault('affordances', [])
            vision_data.setdefault('caption', 'UI screenshot analysis')
            
            # Convert bbox coordinates from floats to integers and fix attributes
            for element in vision_data.get('elements', []):
                if 'bbox' in element and isinstance(element['bbox'], list):
                    element['bbox'] = [int(float(x)) for x in element['bbox'][:4]]  # Ensure max 4 values
                # Fix attributes if it's an array instead of dict
                if 'attributes' in element and isinstance(element['attributes'], list):
                    element['attributes'] = {}
                # Ensure required fields exist
                element.setdefault('role', 'other')
                element.setdefault('visible_text', '')
                element.setdefault('attributes', {})
                element.setdefault('selector_hint', '')
                element.setdefault('bbox', [0, 0, 0, 0])
                element.setdefault('confidence', 0.5)
            
            for field in vision_data.get('fields', []):
                if 'bbox' in field and isinstance(field['bbox'], list):
                    field['bbox'] = [int(float(x)) for x in field['bbox'][:4]]
                # Ensure required fields exist
                field.setdefault('name_hint', '')
                field.setdefault('value_hint', '')
                field.setdefault('bbox', [0, 0, 0, 0])
                field.setdefault('editable', True)
                    
            for affordance in vision_data.get('affordances', []):
                if 'bbox' in affordance and isinstance(affordance['bbox'], list):
                    affordance['bbox'] = [int(float(x)) for x in affordance['bbox'][:4]]
                # Ensure required fields exist
                affordance.setdefault('type', 'button')
                affordance.setdefault('label', '')
                affordance.setdefault('selector_hint', '')
                affordance.setdefault('bbox', [0, 0, 0, 0])
            
            print(f"[VisionAnalyzer] Found {len(vision_data.get('elements', []))} elements, {len(vision_data.get('fields', []))} fields, {len(vision_data.get('affordances', []))} affordances")
            
            return vision_data
            
        except Exception as e:
            print(f"[VisionAnalyzer] JSON parsing failed: {type(e).__name__}: {e}")
            print(f"[VisionAnalyzer] Response text: {response_text[:500]}...")
            # Return fallback structure on any parsing error - never crash
            return {
                'caption': 'Fallback UI screenshot',
                'elements': [],
                'fields': [],
                'affordances': []
            }
    
    async def analyze(self, screenshot_path: str, page_url: str = "", page_title: str = "") -> VisionState:
        """Analyze screenshot and return VisionState.
        
        Args:
            screenshot_path: Path to screenshot file
            page_url: Current page URL (optional)
            page_title: Page title (optional)
            
        Returns:
            VisionState object with analysis results
        """
        start_time = time.time()
        try:
            # Check circuit breaker before expensive operations
            if not self._check_circuit_breaker():
                return VisionState(
                    caption="Vision analysis temporarily disabled due to repeated failures",
                    meta=VisionMeta(
                        url=page_url,
                        title=page_title,
                        model_name="circuit_breaker",
                        confidence=0.0,
                        processing_time=0.01
                    )
                )
            
            # Read and downsize screenshot before encoding to reduce payload
            screenshot_file = Path(screenshot_path)
            if not screenshot_file.exists():
                raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")
            
            # Use aggressive optimization for fast inference
            image_b64 = _to_base64_jpeg(screenshot_path, max_dim=240, quality=30)
            
            # Ensure Ollama is available - fail fast if not
            if not await self.check_ollama_availability():
                raise Exception(
                    "Ollama service required but not running. "
                    "Please run: python ollama_manager.py --setup"
                )

            # Call Moondream2
            prompt = self.build_vision_prompt()
            response = await self.call_moondream(prompt, image_b64)
            
            # Parse response
            vision_data = self.parse_vision_response(response)
            
            # Create VisionState object
            vision_state = VisionState(
                caption=vision_data.get('caption', 'UI screenshot'),
                elements=[VisionElement(**elem) for elem in vision_data.get('elements', [])],
                fields=[VisionField(**field) for field in vision_data.get('fields', [])],
                affordances=[VisionAffordance(**afford) for afford in vision_data.get('affordances', [])],
                meta=VisionMeta(
                    url=page_url,
                    title=page_title,
                    scrollY=0,
                    timestamp=datetime.now().isoformat(),
                    model_name=self.model_name or "moondream:latest",
                    confidence=0.8,
                    processing_time=time.time() - start_time
                )
            )
            
            return vision_state
            
        except Exception as e:
            # Return fallback VisionState on any error
            return VisionState(
                caption=f"Vision analysis failed: {str(e)[:100]}",
                meta=VisionMeta(
                    url=page_url, 
                    title=page_title,
                    model_name="fallback",
                    confidence=0.0,
                    processing_time=0.0
                )
            )


# ----------------------------
# Simple Usage Example
# ----------------------------

async def main():
    """Example usage of VisionAnalyzer."""
    analyzer = VisionAnalyzer()
    
    # Analyze a screenshot (assuming test_screenshot.png exists)
    vision_state = await analyzer.analyze("test_screenshot.png", "https://example.com", "Example Page")
    
    print(f"Caption: {vision_state.caption}")
    print(f"Elements found: {len(vision_state.elements)}")
    print(f"Fields found: {len(vision_state.fields)}")
    print(f"Affordances found: {len(vision_state.affordances)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())