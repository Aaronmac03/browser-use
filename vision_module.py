#!/usr/bin/env python3
"""
Clean Vision Module extracted from successful test_vision.py
Provides simple interface: VisionAnalyzer.analyze(screenshot_path) -> VisionState

Based on successful Phase 1 implementation from aug25.md.
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from pydantic import BaseModel, Field


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
            model_name: Llava-Phi3 model name (auto-resolved if None)
        """
        self.endpoint = endpoint
        self.model_name = model_name
        self._ollama_available = None  # Cache availability check
    
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
    
    async def resolve_llava_phi3_tag(self) -> str:
        """Resolve Llava-Phi3 tag by querying Ollama API and return the exact model tag."""
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
                        if 'llava-phi3' in model_name.lower():
                            print(f"[VisionAnalyzer] Found Llava-Phi3 model: {model_name}")
                            # Return the exact tag as reported by Ollama
                            return model_name or "llava-phi3:latest"
                    
                    print(f"[VisionAnalyzer] No Llava-Phi3 model found, using default")
                    return "llava-phi3:latest"
                else:
                    print(f"[VisionAnalyzer] Failed to get models: HTTP {response.status_code}")
                    return "llava-phi3:latest"
        except Exception as e:
            print(f"[VisionAnalyzer] Error resolving models: {type(e).__name__}: {e}")
            return "llava-phi3:latest"
    
    def build_vision_prompt(self) -> str:
        """Build the vision analysis prompt."""
        return """Analyze this screenshot and extract UI elements as JSON.

Find buttons, links, input fields, text, and interactive elements. Return JSON only:

{
  "caption": "Brief description of the page",
  "elements": [
    {
      "role": "button|link|text|input|other",
      "visible_text": "text shown", 
      "attributes": {},
      "selector_hint": "element description",
      "bbox": [0, 0, 0, 0],
      "confidence": 0.8
    }
  ],
  "fields": [
    {
      "name_hint": "field name",
      "value_hint": "current value", 
      "bbox": [0, 0, 0, 0],
      "editable": true
    }
  ],
  "affordances": [
    {
      "type": "button|link|tab|menu",
      "label": "element label",
      "selector_hint": "how to find it",
      "bbox": [0, 0, 0, 0]
    }
  ]
}"""
    
    async def call_llava_phi3(self, prompt: str, image_b64: str) -> Dict[str, Any]:
        """Call Llava-Phi3 via Ollama API with robust error handling."""
        if not self.model_name:
            self.model_name = await self.resolve_llava_phi3_tag()
            print(f"[VisionAnalyzer] Resolved model name: {self.model_name}")
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "keep_alive": 600,  # keep the model hot
            "options": {"temperature": 0.1}
        }
        
        print(f"[VisionAnalyzer] Calling Llava-Phi3 at {self.endpoint} with model {self.model_name}")
        print(f"[VisionAnalyzer] Image size: {len(image_b64)} characters")
        
        try:
            # Use shorter timeout to fail fast if ollama is not running
            timeout_config = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                # httpx enables keep-alive by default; explicit header for clarity
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json=payload,
                    headers={"Connection": "keep-alive"}
                )
                
                print(f"[VisionAnalyzer] Response status: {response.status_code}")
            
                if response.status_code != 200:
                    error_msg = response.text
                    print(f"[VisionAnalyzer] HTTP Error {response.status_code}: {error_msg[:500]}")
                    
                    # Handle memory issues with fallback response
                    if "system memory" in error_msg.lower() or response.status_code == 500:
                        print(f"[VisionAnalyzer] 🔄 Using memory fallback response")
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
                print(f"[VisionAnalyzer] Got response from local model")
                return response_json
                
        except httpx.TimeoutException as e:
            print(f"[VisionAnalyzer] ⏰ Timeout calling Ollama: {e}")
            print(f"[VisionAnalyzer] 🚨 Ollama may be overloaded or model {self.model_name} not available")
            print(f"[VisionAnalyzer] 🚑 Try: python ollama_manager.py --health")
            raise Exception(f"Ollama timeout - check model availability: python ollama_manager.py --health")
        except httpx.ConnectError as e:
            print(f"[VisionAnalyzer] Connection error to Ollama: {e}")
            print(f"[VisionAnalyzer] 🚨 Ollama service is not running!")
            print(f"[VisionAnalyzer] 🚑 Please run: python ollama_manager.py --setup")
            raise Exception(f"Ollama service required but not running. Run: python ollama_manager.py --setup")
        except json.JSONDecodeError as e:
            print(f"[VisionAnalyzer] 📄 JSON decode error: {e}")
            print(f"[VisionAnalyzer] Raw response: {response.text[:200]}...")
            raise Exception(f"Invalid JSON response from Ollama: {e}")
        except Exception as e:
            print(f"[VisionAnalyzer] Unexpected error: {type(e).__name__}: {e}")
            raise
    
    def parse_vision_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse vision response from Llava-Phi3 with robust error handling."""
        try:
            response_text = response.get('response', '{}')
            print(f"[VisionAnalyzer] Raw response length: {len(response_text)} chars")
            print(f"[VisionAnalyzer] Response preview: {response_text[:200]}...")
            
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
            else:
                json_text = response_text
            
            print(f"[VisionAnalyzer] Extracted JSON length: {len(json_text)} chars")
            
            vision_data = json.loads(json_text)
            print(f"[VisionAnalyzer] Successfully parsed JSON response")
            
            # Validate and set defaults
            if not isinstance(vision_data, dict):
                print(f"[VisionAnalyzer] Response is not a dict, using empty dict")
                vision_data = {}
                
            vision_data.setdefault('elements', [])
            vision_data.setdefault('fields', [])
            vision_data.setdefault('affordances', [])
            vision_data.setdefault('caption', 'UI screenshot analysis')
            
            print(f"[VisionAnalyzer] Found {len(vision_data.get('elements', []))} elements, {len(vision_data.get('fields', []))} fields, {len(vision_data.get('affordances', []))} affordances")
            
            return vision_data
            
        except Exception as e:
            print(f"[VisionAnalyzer] JSON parsing failed: {type(e).__name__}: {e}")
            print(f"[VisionAnalyzer] Response text: {response_text[:500]}...")
            # Return fallback structure on any parsing error
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
        try:
            # Read and downsize screenshot before encoding to reduce payload
            screenshot_file = Path(screenshot_path)
            if not screenshot_file.exists():
                raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")
            
            # Downsize to ~1280px width JPEG quality ~80
            try:
                from PIL import Image  # pillow
                with Image.open(screenshot_file) as img:
                    img = img.convert("RGB")
                    max_width = 1280
                    if img.width > max_width:
                        new_height = int(img.height * (max_width / img.width))
                        img = img.resize((max_width, new_height))
                    import io
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=80, optimize=True)
                    image_bytes = buf.getvalue()
            except Exception:
                # Fallback to raw file bytes if PIL not available
                image_bytes = screenshot_file.read_bytes()
            
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Ensure Ollama is available - fail fast if not
            if not await self.check_ollama_availability():
                raise Exception(
                    "Ollama service required but not running. "
                    "Please run: python ollama_manager.py --setup"
                )

            # Call Llava-Phi3
            prompt = self.build_vision_prompt()
            response = await self.call_llava_phi3(prompt, image_b64)
            
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
                    timestamp=datetime.now().isoformat()
                )
            )
            
            return vision_state
            
        except Exception as e:
            # Return fallback VisionState on any error
            return VisionState(
                caption=f"Vision analysis failed: {str(e)[:100]}",
                meta=VisionMeta(url=page_url, title=page_title)
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