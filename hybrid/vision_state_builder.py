"""
VisionStateBuilder - Core component for local vision processing.

Uses MiniCPM-V 2.6 via Ollama to convert screenshots into structured VisionState JSON.
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import base64
import io
import httpx
from PIL import Image

from .schemas import VisionState, ElementInfo, FieldInfo, AffordanceInfo, PageMeta

logger = logging.getLogger(__name__)


class VisionStateCache:
    """Simple cache for VisionState results to avoid redundant processing"""
    
    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, VisionState] = {}
        self._max_size = max_size
    
    def _compute_screenshot_hash(self, screenshot_data: bytes, viewport_dims: tuple) -> str:
        """Compute hash for screenshot + viewport dimensions"""
        hash_input = screenshot_data + str(viewport_dims).encode()
        return hashlib.md5(hash_input).hexdigest()
    
    def get(self, screenshot_data: bytes, viewport_dims: tuple) -> Optional[VisionState]:
        """Get cached VisionState if available"""
        cache_key = self._compute_screenshot_hash(screenshot_data, viewport_dims)
        return self._cache.get(cache_key)
    
    def set(self, screenshot_data: bytes, viewport_dims: tuple, vision_state: VisionState):
        """Cache VisionState result"""
        cache_key = self._compute_screenshot_hash(screenshot_data, viewport_dims)
        
        # Simple LRU: if cache is full, remove oldest entry
        if len(self._cache) >= self._max_size:
            # Remove first item (oldest)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[cache_key] = vision_state


class VisionStateBuilder:
    """Builds VisionState from screenshots using local MiniCPM-V 2.6"""
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        model_name: str = "minicpm-v:2.6",
        confidence_threshold: float = 0.7,
        use_cache: bool = True
    ):
        self.ollama_base_url = ollama_base_url
        self.model_name = model_name  
        self.confidence_threshold = confidence_threshold
        self.cache = VisionStateCache() if use_cache else None
        
        # HTTP client for Ollama API
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _encode_image_base64(self, image_data: bytes) -> str:
        """Encode image data as base64 string"""
        return base64.b64encode(image_data).decode('utf-8')
    
    def _generate_selector_hint(self, element_data: Dict[str, Any]) -> str:
        """Generate selector hint following the priority order from the brief"""
        
        # Priority 1: Unique visible text
        visible_text = element_data.get('visible_text', '').strip()
        if visible_text and len(visible_text) < 50:
            element_type = element_data.get('role', 'element')
            return f"{element_type}:contains('{visible_text}')"
        
        # Priority 2: Aria labels
        attributes = element_data.get('attributes', {})
        aria_label = attributes.get('ariaLabel')
        if aria_label:
            return f"[aria-label='{aria_label}']"
        
        # Priority 3: Position + type
        role = element_data.get('role', 'element')
        position_hint = element_data.get('position_hint', '')
        if position_hint:
            return f"{role} {position_hint}"
        
        # Priority 4: Visual position (relative to other elements)
        bbox = element_data.get('bbox', [0, 0, 0, 0])
        return f"{role} near top-left({bbox[0]},{bbox[1]})"
    
    async def _call_ollama_vision(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Call Ollama with vision model"""
        base64_image = self._encode_image_base64(image_data)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [base64_image],
            "stream": False,
            "format": "json"
        }
        
        try:
            response = await self.client.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Parse the JSON response from the model
            response_text = result.get('response', '{}')
            return json.loads(response_text)
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Ollama: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            raise
    
    async def build_vision_state(
        self,
        screenshot_data: bytes,
        url: str,
        title: str,
        viewport_dims: tuple = (1280, 720),
        scroll_y: int = 0
    ) -> VisionState:
        """Build VisionState from screenshot data"""
        
        # Check cache first
        if self.cache:
            cached_result = self.cache.get(screenshot_data, viewport_dims)
            if cached_result:
                logger.info("Returning cached VisionState")
                return cached_result
        
        # Prepare the vision prompt
        vision_prompt = self._create_vision_prompt()
        
        try:
            # Call local VLM
            raw_result = await self._call_ollama_vision(screenshot_data, vision_prompt)
            
            # Process and structure the result
            vision_state = self._process_vision_result(
                raw_result, url, title, scroll_y
            )
            
            # Cache the result
            if self.cache:
                self.cache.set(screenshot_data, viewport_dims, vision_state)
            
            logger.info(f"Generated VisionState with {len(vision_state.elements)} elements")
            return vision_state
            
        except Exception as e:
            logger.error(f"Failed to build VisionState: {e}")
            # Return minimal fallback VisionState
            return VisionState(
                caption="Vision processing failed",
                elements=[],
                fields=[],
                affordances=[],
                meta=PageMeta(url=url, title=title, scrollY=scroll_y)
            )
    
    def _create_vision_prompt(self) -> str:
        """Create the prompt for the vision model"""
        return """
Analyze this screenshot and extract UI elements in JSON format.

Return a JSON object with:
- "caption": Brief description (max 200 chars)  
- "elements": Array of UI elements with:
  - "role": "button"|"link"|"text"|"image"|"input"|"other"
  - "visible_text": Text content if any
  - "attributes": Object with any aria-label, type, etc.
  - "bbox": [x, y, width, height] coordinates
  - "confidence": 0.0-1.0 confidence score
  - "position_hint": Description of position like "header", "footer", "first", etc.
- "fields": Array of form fields with:
  - "name_hint": Field name/purpose like "email", "password"
  - "value_hint": Current value if visible
  - "bbox": [x, y, width, height]
  - "editable": true/false
- "affordances": Array of interactive elements with:
  - "type": "button"|"link"|"tab"|"menu"|"icon"  
  - "label": Visible label or description
  - "bbox": [x, y, width, height]

Focus on interactive elements users can click/type in. Use high confidence (>0.8) for clear elements only.
"""
    
    def _process_vision_result(
        self,
        raw_result: Dict[str, Any],
        url: str,
        title: str,
        scroll_y: int
    ) -> VisionState:
        """Process raw vision model result into VisionState"""
        
        # Extract and process elements
        elements = []
        for elem_data in raw_result.get('elements', []):
            try:
                element = ElementInfo(
                    role=elem_data.get('role', 'other'),
                    visible_text=elem_data.get('visible_text', ''),
                    attributes=elem_data.get('attributes', {}),
                    selector_hint=self._generate_selector_hint(elem_data),
                    bbox=elem_data.get('bbox', [0, 0, 0, 0]),
                    confidence=elem_data.get('confidence', 0.5)
                )
                # Only include elements above confidence threshold
                if element.confidence >= self.confidence_threshold:
                    elements.append(element)
            except Exception as e:
                logger.warning(f"Skipping invalid element: {e}")
        
        # Extract and process fields
        fields = []
        for field_data in raw_result.get('fields', []):
            try:
                field = FieldInfo(
                    name_hint=field_data.get('name_hint', ''),
                    value_hint=field_data.get('value_hint', ''),
                    bbox=field_data.get('bbox', [0, 0, 0, 0]),
                    editable=field_data.get('editable', True)
                )
                fields.append(field)
            except Exception as e:
                logger.warning(f"Skipping invalid field: {e}")
        
        # Extract and process affordances
        affordances = []
        for aff_data in raw_result.get('affordances', []):
            try:
                affordance = AffordanceInfo(
                    type=aff_data.get('type', 'button'),
                    label=aff_data.get('label', ''),
                    selector_hint=self._generate_selector_hint(aff_data),
                    bbox=aff_data.get('bbox', [0, 0, 0, 0])
                )
                affordances.append(affordance)
            except Exception as e:
                logger.warning(f"Skipping invalid affordance: {e}")
        
        return VisionState(
            caption=raw_result.get('caption', 'Page analysis')[:200],
            elements=elements,
            fields=fields,
            affordances=affordances,
            meta=PageMeta(url=url, title=title, scrollY=scroll_y)
        )