"""
LocalActionHeuristics - Determines if actions can be handled locally.

Implements simple heuristics to decide when to handle click/type/scroll locally
vs escalating to cloud reasoning.
"""

import logging
from typing import Optional, List, Tuple
import re
from difflib import SequenceMatcher

from .schemas import VisionState, Action, ActionTarget, ElementInfo, FieldInfo, AffordanceInfo

logger = logging.getLogger(__name__)


class LocalActionHeuristics:
    """Determines if actions can be handled locally without cloud reasoning"""
    
    def __init__(
        self,
        confidence_threshold: float = 0.8,
        similarity_threshold: float = 0.8,
        max_ambiguous_matches: int = 1
    ):
        self.confidence_threshold = confidence_threshold
        self.similarity_threshold = similarity_threshold  
        self.max_ambiguous_matches = max_ambiguous_matches
    
    def can_handle_locally(
        self,
        intent: str,
        vision_state: VisionState
    ) -> Tuple[bool, Optional[Action], str]:
        """
        Determine if intent can be handled locally.
        
        Returns:
            (can_handle, action, reason)
        """
        
        # Parse the intent to extract action type and target
        action_info = self._parse_intent(intent)
        if not action_info:
            return False, None, "Could not parse intent"
        
        action_type, target_description, value = action_info
        
        # Handle different action types
        if action_type in ["click", "hover"]:
            return self._handle_click_action(target_description, vision_state, action_type)
        elif action_type == "type":
            return self._handle_type_action(target_description, value, vision_state)
        elif action_type == "scroll":
            return self._handle_scroll_action(target_description, value, vision_state)
        elif action_type == "navigate":
            return self._handle_navigate_action(value, vision_state)
        else:
            return False, None, f"Action type '{action_type}' not supported locally"
    
    def _parse_intent(self, intent: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """Parse natural language intent into (action_type, target, value)"""
        
        intent_lower = intent.lower().strip()
        
        # Click patterns
        click_patterns = [
            r"click (?:on )?(?:the )?(.+)",
            r"press (?:the )?(.+)",
            r"select (?:the )?(.+)",
            r"tap (?:on )?(?:the )?(.+)"
        ]
        
        for pattern in click_patterns:
            match = re.search(pattern, intent_lower)
            if match:
                target = match.group(1).strip()
                return "click", target, None
        
        # Type patterns
        type_patterns = [
            r"type [\"'](.+)[\"'] (?:in|into) (?:the )?(.+)",
            r"enter [\"'](.+)[\"'] (?:in|into) (?:the )?(.+)",
            r"fill (?:the )?(.+) with [\"'](.+)[\"']",
            r"input [\"'](.+)[\"'] (?:in|into) (?:the )?(.+)"
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, intent_lower)
            if match:
                if "fill" in pattern:
                    # For fill pattern, order is reversed
                    target, value = match.groups()
                else:
                    value, target = match.groups()
                return "type", target.strip(), value.strip()
        
        # Scroll patterns
        scroll_patterns = [
            r"scroll (up|down|left|right)",
            r"scroll (?:to )?(?:the )?(top|bottom)",
            r"page (up|down)"
        ]
        
        for pattern in scroll_patterns:
            match = re.search(pattern, intent_lower)
            if match:
                direction = match.group(1)
                return "scroll", "", direction
        
        # Navigate patterns
        nav_patterns = [
            r"(?:go to|navigate to|visit|open) (.+)",
            r"load (?:the page )?(.+)"
        ]
        
        for pattern in nav_patterns:
            match = re.search(pattern, intent_lower)
            if match:
                url = match.group(1).strip()
                return "navigate", "", url
        
        return None
    
    def _handle_click_action(
        self,
        target_description: str,
        vision_state: VisionState,
        action_type: str
    ) -> Tuple[bool, Optional[Action], str]:
        """Handle click/hover actions"""
        
        # Look for matches in elements and affordances
        element_matches = self._find_matching_elements(target_description, vision_state.elements)
        affordance_matches = self._find_matching_affordances(target_description, vision_state.affordances)
        
        all_matches = element_matches + affordance_matches
        
        if not all_matches:
            return False, None, f"No elements found matching '{target_description}'"
        
        # Filter by confidence
        high_confidence_matches = [
            match for match in all_matches
            if match[1] >= self.confidence_threshold
        ]
        
        if not high_confidence_matches:
            return False, None, f"No high-confidence matches for '{target_description}'"
        
        if len(high_confidence_matches) > self.max_ambiguous_matches:
            return False, None, f"Too many ambiguous matches ({len(high_confidence_matches)}), need cloud reasoning"
        
        # Use the best match
        best_match = max(high_confidence_matches, key=lambda x: x[1])
        selector_hint, confidence = best_match[0], best_match[1]
        
        action = Action(
            op=action_type,
            target=ActionTarget(selector_hint=selector_hint),
            notes=f"Local match with confidence {confidence:.2f}"
        )
        
        return True, action, f"Found unambiguous match with confidence {confidence:.2f}"
    
    def _handle_type_action(
        self,
        target_description: str,
        value: str,
        vision_state: VisionState
    ) -> Tuple[bool, Optional[Action], str]:
        """Handle type actions"""
        
        # Look for matching input fields
        field_matches = self._find_matching_fields(target_description, vision_state.fields)
        element_matches = [
            (elem.selector_hint, elem.confidence)
            for elem in vision_state.elements
            if elem.role == "input" and self._text_similarity(target_description, elem.visible_text) > self.similarity_threshold
        ]
        
        all_matches = field_matches + element_matches
        
        if not all_matches:
            return False, None, f"No input fields found matching '{target_description}'"
        
        high_confidence_matches = [
            match for match in all_matches
            if match[1] >= self.confidence_threshold
        ]
        
        if not high_confidence_matches:
            return False, None, f"No high-confidence field matches for '{target_description}'"
        
        if len(high_confidence_matches) > self.max_ambiguous_matches:
            return False, None, f"Multiple field matches, need disambiguation"
        
        best_match = max(high_confidence_matches, key=lambda x: x[1])
        selector_hint, confidence = best_match[0], best_match[1]
        
        action = Action(
            op="type",
            target=ActionTarget(selector_hint=selector_hint),
            value=value,
            notes=f"Local field match with confidence {confidence:.2f}"
        )
        
        return True, action, f"Found field match with confidence {confidence:.2f}"
    
    def _handle_scroll_action(
        self,
        target_description: str,
        direction: str,
        vision_state: VisionState
    ) -> Tuple[bool, Optional[Action], str]:
        """Handle scroll actions"""
        
        # Scrolling is usually unambiguous and can be handled locally
        scroll_value = {
            "up": "up",
            "down": "down", 
            "left": "left",
            "right": "right",
            "top": "top",
            "bottom": "bottom"
        }.get(direction.lower())
        
        if not scroll_value:
            return False, None, f"Unknown scroll direction: {direction}"
        
        action = Action(
            op="scroll",
            value=scroll_value,
            notes="Simple scroll action handled locally"
        )
        
        return True, action, f"Scroll {direction} handled locally"
    
    def _handle_navigate_action(
        self,
        url: str,
        vision_state: VisionState
    ) -> Tuple[bool, Optional[Action], str]:
        """Handle navigation actions"""
        
        # Basic URL validation
        if not url:
            return False, None, "No URL provided"
        
        # Add protocol if missing
        if not url.startswith(("http://", "https://", "file://")):
            if url.startswith("www.") or "." in url:
                url = f"https://{url}"
            else:
                return False, None, f"Invalid URL format: {url}"
        
        action = Action(
            op="navigate",
            value=url,
            notes="Simple navigation handled locally"
        )
        
        return True, action, f"Navigation to {url} handled locally"
    
    def _find_matching_elements(
        self,
        target_description: str,
        elements: List[ElementInfo]
    ) -> List[Tuple[str, float]]:
        """Find elements matching the target description"""
        
        matches = []
        for element in elements:
            # Check visible text similarity
            text_score = self._text_similarity(target_description, element.visible_text)
            
            # Check attributes (aria-label, etc.)  
            attr_score = 0.0
            for attr_value in element.attributes.values():
                if isinstance(attr_value, str):
                    attr_score = max(attr_score, self._text_similarity(target_description, attr_value))
            
            # Use the best score
            best_score = max(text_score, attr_score)
            
            if best_score > 0.3:  # Minimum threshold for consideration
                # Combine with element confidence
                final_confidence = (best_score + element.confidence) / 2
                matches.append((element.selector_hint, final_confidence))
        
        return matches
    
    def _find_matching_affordances(
        self,
        target_description: str,
        affordances: List[AffordanceInfo]
    ) -> List[Tuple[str, float]]:
        """Find affordances matching the target description"""
        
        matches = []
        for affordance in affordances:
            text_score = self._text_similarity(target_description, affordance.label)
            
            if text_score > 0.3:
                # Affordances don't have explicit confidence, so use text similarity
                matches.append((affordance.selector_hint, text_score))
        
        return matches
    
    def _find_matching_fields(
        self,
        target_description: str,
        fields: List[FieldInfo]
    ) -> List[Tuple[str, float]]:
        """Find fields matching the target description"""
        
        matches = []
        for field in fields:
            if not field.editable:
                continue
                
            name_score = self._text_similarity(target_description, field.name_hint)
            
            if name_score > 0.3:
                matches.append((f"input[name*='{field.name_hint}']", name_score))
        
        return matches
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using sequence matcher"""
        if not text1 or not text2:
            return 0.0
        
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()