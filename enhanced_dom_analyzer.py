#!/usr/bin/env python3
"""
Enhanced DOM Analyzer - Fast, reliable element detection without ML dependencies
Serves as Tier 1 in the multi-model vision pipeline
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from playwright.async_api import Page, ElementHandle

# Import vision schemas from existing module
from vision_module import VisionState, VisionElement, VisionField, VisionAffordance, VisionMeta


class DOMElementInfo(BaseModel):
    """Raw DOM element information"""
    tag_name: str
    text_content: str
    visible_text: str
    attributes: Dict[str, str]
    bbox: List[int]
    is_visible: bool
    is_interactive: bool
    selector: str
    xpath: str


class EnhancedDOMAnalyzer:
    """Fast, reliable DOM-based element detection and analysis"""
    
    def __init__(self):
        self.performance_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'avg_response_time': 0.0,
            'last_analysis_time': None
        }
    
    async def analyze_page(self, page: Page, page_url: str = "", page_title: str = "") -> VisionState:
        """Analyze page using DOM inspection and visual heuristics"""
        start_time = time.time()
        
        try:
            self.performance_stats['total_calls'] += 1
            
            # Get page metadata
            if not page_url:
                page_url = page.url
            if not page_title:
                page_title = await page.title()
            
            # Extract all interactive elements
            elements = await self._extract_interactive_elements(page)
            
            # Extract form fields
            fields = await self._extract_form_fields(page)
            
            # Extract affordances (buttons, links, etc.)
            affordances = await self._extract_affordances(page)
            
            # Generate page caption
            caption = await self._generate_page_caption(page, page_title, elements, fields)
            
            # Get scroll position
            scroll_y = await page.evaluate("window.pageYOffset")
            
            processing_time = time.time() - start_time
            self.performance_stats['successful_calls'] += 1
            self.performance_stats['last_analysis_time'] = processing_time
            
            # Update rolling average
            total_successful = self.performance_stats['successful_calls']
            current_avg = self.performance_stats['avg_response_time']
            self.performance_stats['avg_response_time'] = (
                (current_avg * (total_successful - 1) + processing_time) / total_successful
            )
            
            print(f"[EnhancedDOMAnalyzer] Analysis completed in {processing_time:.3f}s")
            print(f"[EnhancedDOMAnalyzer] Found {len(elements)} elements, {len(fields)} fields, {len(affordances)} affordances")
            
            return VisionState(
                caption=caption,
                elements=elements,
                fields=fields,
                affordances=affordances,
                meta=VisionMeta(
                    url=page_url,
                    title=page_title,
                    scrollY=scroll_y,
                    timestamp=datetime.now().isoformat(),
                    model_name="enhanced_dom_analyzer",
                    confidence=0.9,  # High confidence for DOM-based analysis
                    processing_time=processing_time
                )
            )
            
        except Exception as e:
            print(f"[EnhancedDOMAnalyzer] Analysis failed: {e}")
            return VisionState(
                caption=f"DOM analysis failed: {str(e)[:100]}",
                meta=VisionMeta(
                    url=page_url,
                    title=page_title,
                    model_name="enhanced_dom_analyzer_fallback",
                    confidence=0.0,
                    processing_time=time.time() - start_time
                )
            )
    
    async def _extract_interactive_elements(self, page: Page) -> List[VisionElement]:
        """Extract all interactive elements from the page"""
        elements = []
        
        # Define interactive selectors with priorities
        interactive_selectors = [
            # High priority - common interactive elements
            ('button', 'button'),
            ('a[href]', 'link'),
            ('input[type="submit"]', 'button'),
            ('input[type="button"]', 'button'),
            ('[role="button"]', 'button'),
            ('[onclick]', 'button'),
            
            # Medium priority - form elements
            ('input[type="text"]', 'text'),
            ('input[type="email"]', 'text'),
            ('input[type="password"]', 'text'),
            ('input[type="search"]', 'text'),
            ('textarea', 'text'),
            ('select', 'other'),
            ('input[type="checkbox"]', 'other'),
            ('input[type="radio"]', 'other'),
            
            # Lower priority - other interactive elements
            ('[tabindex]', 'other'),
            ('[draggable="true"]', 'other'),
        ]
        
        for selector, role in interactive_selectors:
            try:
                element_handles = await page.query_selector_all(selector)
                
                for handle in element_handles:
                    try:
                        element_info = await self._extract_element_info(handle, role)
                        if element_info and element_info.is_visible:
                            vision_element = VisionElement(
                                role=role,
                                visible_text=element_info.visible_text,
                                attributes=element_info.attributes,
                                selector_hint=element_info.selector,
                                bbox=element_info.bbox,
                                confidence=0.9
                            )
                            elements.append(vision_element)
                    except Exception as e:
                        print(f"[EnhancedDOMAnalyzer] Error processing element: {e}")
                        continue
                        
            except Exception as e:
                print(f"[EnhancedDOMAnalyzer] Error with selector {selector}: {e}")
                continue
        
        # Remove duplicates based on bbox and text
        unique_elements = self._deduplicate_elements(elements)
        
        return unique_elements[:20]  # Limit to top 20 elements
    
    async def _extract_form_fields(self, page: Page) -> List[VisionField]:
        """Extract form fields with enhanced detection"""
        fields = []
        
        field_selectors = [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="password"]',
            'input[type="search"]',
            'input[type="tel"]',
            'input[type="url"]',
            'input[type="number"]',
            'textarea',
            'select'
        ]
        
        for selector in field_selectors:
            try:
                field_handles = await page.query_selector_all(selector)
                
                for handle in field_handles:
                    try:
                        element_info = await self._extract_element_info(handle, 'field')
                        if element_info and element_info.is_visible:
                            # Get field name hint from various sources
                            name_hint = await self._get_field_name_hint(handle)
                            
                            # Get current value
                            value_hint = element_info.attributes.get('value', '')
                            if not value_hint:
                                value_hint = await handle.input_value() if await handle.is_enabled() else ''
                            
                            vision_field = VisionField(
                                name_hint=name_hint,
                                value_hint=value_hint,
                                bbox=element_info.bbox,
                                editable=await handle.is_enabled()
                            )
                            fields.append(vision_field)
                            
                    except Exception as e:
                        print(f"[EnhancedDOMAnalyzer] Error processing field: {e}")
                        continue
                        
            except Exception as e:
                print(f"[EnhancedDOMAnalyzer] Error with field selector {selector}: {e}")
                continue
        
        return fields[:10]  # Limit to top 10 fields
    
    async def _extract_affordances(self, page: Page) -> List[VisionAffordance]:
        """Extract interactive affordances (buttons, links, etc.)"""
        affordances = []
        
        affordance_selectors = [
            ('button', 'button'),
            ('a[href]', 'link'),
            ('input[type="submit"]', 'button'),
            ('[role="button"]', 'button'),
            ('[role="tab"]', 'tab'),
            ('[role="menuitem"]', 'menu'),
            ('.btn', 'button'),
            ('.button', 'button'),
            ('.link', 'link')
        ]
        
        for selector, affordance_type in affordance_selectors:
            try:
                element_handles = await page.query_selector_all(selector)
                
                for handle in element_handles:
                    try:
                        element_info = await self._extract_element_info(handle, affordance_type)
                        if element_info and element_info.is_visible:
                            vision_affordance = VisionAffordance(
                                type=affordance_type,
                                label=element_info.visible_text or element_info.attributes.get('aria-label', ''),
                                selector_hint=element_info.selector,
                                bbox=element_info.bbox
                            )
                            affordances.append(vision_affordance)
                            
                    except Exception as e:
                        print(f"[EnhancedDOMAnalyzer] Error processing affordance: {e}")
                        continue
                        
            except Exception as e:
                print(f"[EnhancedDOMAnalyzer] Error with affordance selector {selector}: {e}")
                continue
        
        # Remove duplicates
        unique_affordances = self._deduplicate_affordances(affordances)
        
        return unique_affordances[:15]  # Limit to top 15 affordances
    
    async def _extract_element_info(self, handle: ElementHandle, role: str) -> Optional[DOMElementInfo]:
        """Extract comprehensive information about a DOM element"""
        try:
            # Check if element is visible
            is_visible = await handle.is_visible()
            if not is_visible:
                return None
            
            # Get basic properties
            tag_name = await handle.evaluate("el => el.tagName.toLowerCase()")
            text_content = await handle.text_content() or ""
            visible_text = text_content.strip()[:100]  # Limit text length
            
            # Get all attributes
            attributes = await handle.evaluate("""
                el => {
                    const attrs = {};
                    for (let attr of el.attributes) {
                        attrs[attr.name] = attr.value;
                    }
                    return attrs;
                }
            """)
            
            # Get bounding box
            bbox_data = await handle.bounding_box()
            bbox = [0, 0, 0, 0]
            if bbox_data:
                bbox = [
                    int(bbox_data['x']),
                    int(bbox_data['y']),
                    int(bbox_data['width']),
                    int(bbox_data['height'])
                ]
            
            # Generate reliable selector
            selector = await self._generate_reliable_selector(handle, visible_text, attributes)
            
            # Generate XPath
            xpath = await handle.evaluate("""
                el => {
                    const getXPath = (element) => {
                        if (element.id) return `//*[@id="${element.id}"]`;
                        if (element === document.body) return '/html/body';
                        
                        let ix = 0;
                        const siblings = element.parentNode?.childNodes || [];
                        for (let i = 0; i < siblings.length; i++) {
                            const sibling = siblings[i];
                            if (sibling === element) {
                                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                                ix++;
                            }
                        }
                    };
                    return getXPath(el);
                }
            """)
            
            # Determine if element is interactive
            is_interactive = await self._is_element_interactive(handle, tag_name, attributes)
            
            return DOMElementInfo(
                tag_name=tag_name,
                text_content=text_content,
                visible_text=visible_text,
                attributes=attributes,
                bbox=bbox,
                is_visible=is_visible,
                is_interactive=is_interactive,
                selector=selector,
                xpath=xpath or ""
            )
            
        except Exception as e:
            print(f"[EnhancedDOMAnalyzer] Error extracting element info: {e}")
            return None
    
    async def _generate_reliable_selector(self, handle: ElementHandle, visible_text: str, attributes: Dict[str, str]) -> str:
        """Generate the most reliable CSS selector for an element"""
        
        # Priority 1: ID selector
        if attributes.get('id'):
            return f"#{attributes['id']}"
        
        # Priority 2: Unique text content
        if visible_text and len(visible_text) > 2:
            # Escape quotes and special characters
            escaped_text = visible_text.replace('"', '\\"').replace("'", "\\'")
            return f"*:contains('{escaped_text[:50]}')"
        
        # Priority 3: Aria-label
        if attributes.get('aria-label'):
            aria_label = attributes['aria-label'].replace('"', '\\"')
            return f"[aria-label=\"{aria_label}\"]"
        
        # Priority 4: Name attribute
        if attributes.get('name'):
            return f"[name=\"{attributes['name']}\"]"
        
        # Priority 5: Class-based selector
        if attributes.get('class'):
            classes = attributes['class'].split()
            if classes:
                # Use first class that looks meaningful
                for cls in classes:
                    if len(cls) > 2 and not cls.startswith('_'):
                        return f".{cls}"
        
        # Priority 6: Type and tag combination
        tag_name = await handle.evaluate("el => el.tagName.toLowerCase()")
        if attributes.get('type'):
            return f"{tag_name}[type=\"{attributes['type']}\"]"
        
        # Priority 7: Generic tag selector
        return tag_name
    
    async def _is_element_interactive(self, handle: ElementHandle, tag_name: str, attributes: Dict[str, str]) -> bool:
        """Determine if an element is interactive"""
        
        # Interactive tags
        interactive_tags = {'button', 'a', 'input', 'select', 'textarea'}
        if tag_name in interactive_tags:
            return True
        
        # Interactive attributes
        interactive_attrs = {'onclick', 'onchange', 'role', 'tabindex'}
        if any(attr in attributes for attr in interactive_attrs):
            return True
        
        # Interactive roles
        interactive_roles = {'button', 'link', 'tab', 'menuitem', 'option'}
        if attributes.get('role') in interactive_roles:
            return True
        
        # Check if element is clickable via JavaScript
        try:
            is_clickable = await handle.evaluate("""
                el => {
                    const style = window.getComputedStyle(el);
                    return style.cursor === 'pointer' || 
                           el.onclick !== null ||
                           el.getAttribute('onclick') !== null;
                }
            """)
            return is_clickable
        except:
            return False
    
    async def _get_field_name_hint(self, handle: ElementHandle) -> str:
        """Get a meaningful name hint for a form field"""
        
        # Try various methods to get field name
        name_sources = [
            lambda: handle.get_attribute('name'),
            lambda: handle.get_attribute('id'),
            lambda: handle.get_attribute('placeholder'),
            lambda: handle.get_attribute('aria-label'),
            lambda: handle.get_attribute('title'),
        ]
        
        for source in name_sources:
            try:
                name = await source()
                if name and len(name.strip()) > 0:
                    return name.strip()[:50]
            except:
                continue
        
        # Try to find associated label
        try:
            label_text = await handle.evaluate("""
                el => {
                    // Look for label by 'for' attribute
                    if (el.id) {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        if (label) return label.textContent.trim();
                    }
                    
                    // Look for parent label
                    let parent = el.parentElement;
                    while (parent && parent.tagName !== 'BODY') {
                        if (parent.tagName === 'LABEL') {
                            return parent.textContent.trim();
                        }
                        parent = parent.parentElement;
                    }
                    
                    // Look for preceding text
                    const prev = el.previousElementSibling;
                    if (prev && prev.textContent) {
                        return prev.textContent.trim();
                    }
                    
                    return '';
                }
            """)
            
            if label_text:
                return label_text[:50]
                
        except:
            pass
        
        return "field"
    
    async def _generate_page_caption(self, page: Page, title: str, elements: List[VisionElement], fields: List[VisionField]) -> str:
        """Generate a descriptive caption for the page"""
        
        try:
            # Get page URL for context
            url = page.url
            domain = urlparse(url).netloc
            
            # Count different types of elements
            buttons = len([e for e in elements if e.role == 'button'])
            links = len([e for e in elements if e.role == 'link'])
            form_fields = len(fields)
            
            # Generate contextual caption
            if form_fields > 2:
                return f"{title} - Form page with {form_fields} fields on {domain}"
            elif buttons > 3:
                return f"{title} - Interactive page with {buttons} buttons on {domain}"
            elif links > 5:
                return f"{title} - Navigation page with {links} links on {domain}"
            else:
                return f"{title} - Web page on {domain}"
                
        except:
            return f"Web page analysis - {len(elements)} interactive elements detected"
    
    def _deduplicate_elements(self, elements: List[VisionElement]) -> List[VisionElement]:
        """Remove duplicate elements based on position and text"""
        unique_elements = []
        seen_signatures = set()
        
        for element in elements:
            # Create signature based on bbox and text
            signature = (
                tuple(element.bbox),
                element.visible_text[:20],
                element.role
            )
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_elements.append(element)
        
        return unique_elements
    
    def _deduplicate_affordances(self, affordances: List[VisionAffordance]) -> List[VisionAffordance]:
        """Remove duplicate affordances"""
        unique_affordances = []
        seen_signatures = set()
        
        for affordance in affordances:
            signature = (
                tuple(affordance.bbox),
                affordance.label[:20],
                affordance.type
            )
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_affordances.append(affordance)
        
        return unique_affordances
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        success_rate = (self.performance_stats['successful_calls'] / 
                       max(1, self.performance_stats['total_calls']))
        
        return {
            'total_calls': self.performance_stats['total_calls'],
            'successful_calls': self.performance_stats['successful_calls'],
            'success_rate': success_rate,
            'avg_response_time': self.performance_stats['avg_response_time'],
            'last_analysis_time': self.performance_stats['last_analysis_time']
        }


# Test function
async def test_enhanced_dom_analyzer():
    """Test the enhanced DOM analyzer"""
    from playwright.async_api import async_playwright
    
    analyzer = EnhancedDOMAnalyzer()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Test with a simple page
        await page.goto("https://example.com")
        
        vision_state = await analyzer.analyze_page(page)
        
        print(f"Caption: {vision_state.caption}")
        print(f"Elements: {len(vision_state.elements)}")
        print(f"Fields: {len(vision_state.fields)}")
        print(f"Affordances: {len(vision_state.affordances)}")
        print(f"Processing time: {vision_state.meta.processing_time:.3f}s")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_enhanced_dom_analyzer())