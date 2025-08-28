"""
Action Classifier for determining vision requirements in browser automation tasks.

This module analyzes browser automation tasks to determine whether they require
vision capabilities or can be handled with text-only models when DOM state is available.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum

from config.models import TaskComplexity


class ActionType(str, Enum):
    """Types of browser actions."""
    NAVIGATION = "navigation"           # go_to_url, go_back, refresh
    FORM_INTERACTION = "form_interaction"  # input_text, click_element (with index)
    ELEMENT_SELECTION = "element_selection"  # Click by description, find elements
    CONTENT_EXTRACTION = "content_extraction"  # extract_structured_data
    KEYBOARD_INPUT = "keyboard_input"   # send_keys, shortcuts
    TAB_MANAGEMENT = "tab_management"   # switch_tab, close_tab
    SCROLLING = "scrolling"            # scroll up/down
    VISUAL_ANALYSIS = "visual_analysis"  # "find the blue button", complex page analysis
    DROPDOWN_INTERACTION = "dropdown_interaction"  # select_dropdown_option (with index)
    FILE_OPERATIONS = "file_operations"  # upload_file, download


@dataclass
class ActionAnalysis:
    """Result of action analysis."""
    action_type: ActionType
    requires_vision: bool
    confidence_score: float  # 0.0 to 1.0
    reasoning: str
    complexity: TaskComplexity = TaskComplexity.SIMPLE


class ActionClassifier:
    """Classifier for determining vision requirements of browser actions."""
    
    def __init__(self):
        """Initialize the action classifier."""
        self.logger = logging.getLogger(__name__)
        
        # Patterns that definitely don't need vision (when DOM state available)
        self._text_only_patterns = {
            # Navigation patterns
            r'go to\s+(?:url\s+)?["\']?https?://': ActionType.NAVIGATION,
            r'navigate to\s+["\']?https?://': ActionType.NAVIGATION,
            r'open\s+["\']?https?://': ActionType.NAVIGATION,
            r'visit\s+["\']?https?://': ActionType.NAVIGATION,
            r'go back|navigate back': ActionType.NAVIGATION,
            
            # Form interaction with index
            r'click element\s+(?:with\s+)?(?:index\s+)?\d+': ActionType.FORM_INTERACTION,
            r'input text.*(?:index\s+)?\d+': ActionType.FORM_INTERACTION,
            r'type.*(?:into|in).*(?:index\s+)?\d+': ActionType.FORM_INTERACTION,
            r'fill.*(?:index\s+)?\d+': ActionType.FORM_INTERACTION,
            
            # Keyboard shortcuts
            r'press\s+(?:ctrl|cmd|alt|shift)\+': ActionType.KEYBOARD_INPUT,
            r'send keys?\s+': ActionType.KEYBOARD_INPUT,
            r'keyboard shortcut': ActionType.KEYBOARD_INPUT,
            
            # Tab management
            r'switch to tab\s+\d+': ActionType.TAB_MANAGEMENT,
            r'close tab\s+\d+': ActionType.TAB_MANAGEMENT,
            r'open new tab': ActionType.TAB_MANAGEMENT,
            
            # Scrolling
            r'scroll\s+(?:up|down)': ActionType.SCROLLING,
            r'scroll.*page': ActionType.SCROLLING,
            
            # Dropdown with index
            r'select.*dropdown.*(?:index\s+)?\d+': ActionType.DROPDOWN_INTERACTION,
        }
        
        # Patterns that definitely need vision
        self._vision_required_patterns = {
            # Visual element identification
            r'find.*(?:button|link|field|element)': ActionType.VISUAL_ANALYSIS,
            r'look for.*(?:button|link|field|element)': ActionType.VISUAL_ANALYSIS,
            r'locate.*(?:button|link|field|element)': ActionType.VISUAL_ANALYSIS,
            r'identify.*(?:button|link|field|element)': ActionType.VISUAL_ANALYSIS,
            
            # Color/visual descriptions
            r'(?:blue|red|green|yellow|orange|purple|gray|white|black)\s+(?:button|link)': ActionType.VISUAL_ANALYSIS,
            r'(?:big|small|large|tiny)\s+(?:button|link)': ActionType.VISUAL_ANALYSIS,
            r'(?:top|bottom|left|right)\s+(?:corner|side)': ActionType.VISUAL_ANALYSIS,
            
            # Position-based selection
            r'(?:first|second|third|last)\s+(?:button|link|element)': ActionType.VISUAL_ANALYSIS,
            r'(?:next to|near|above|below)': ActionType.VISUAL_ANALYSIS,
            
            # Complex analysis
            r'analyze.*(?:page|content|layout)': ActionType.VISUAL_ANALYSIS,
            r'screenshot': ActionType.VISUAL_ANALYSIS,
            r'what.*(?:see|visible)': ActionType.VISUAL_ANALYSIS,
        }
        
        # Keywords that suggest DOM state might be sufficient
        self._dom_sufficient_keywords = {
            'index', 'element', 'selector', 'xpath', 'css', 'id', 'class', 'name'
        }
        
        # Keywords that definitely require vision
        self._vision_required_keywords = {
            'find', 'look', 'locate', 'identify', 'visual', 'color', 'image',
            'button', 'click', 'visible', 'screenshot', 'appearance', 'layout'
        }
    
    def classify_action(
        self, 
        task_description: str, 
        has_dom_state: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> ActionAnalysis:
        """
        Classify whether an action requires vision capabilities.
        
        Args:
            task_description: Description of the task/action
            has_dom_state: Whether DOM state with indexed elements is available
            context: Optional context information
            
        Returns:
            ActionAnalysis with classification results
        """
        task_lower = task_description.lower().strip()
        
        # Check for explicit text-only patterns first
        for pattern, action_type in self._text_only_patterns.items():
            if re.search(pattern, task_lower):
                return ActionAnalysis(
                    action_type=action_type,
                    requires_vision=False,
                    confidence_score=0.9,
                    reasoning=f"Matched text-only pattern: {pattern}",
                    complexity=TaskComplexity.SIMPLE
                )
        
        # Check for explicit vision-required patterns
        for pattern, action_type in self._vision_required_patterns.items():
            if re.search(pattern, task_lower):
                return ActionAnalysis(
                    action_type=action_type,
                    requires_vision=True,
                    confidence_score=0.9,
                    reasoning=f"Matched vision-required pattern: {pattern}",
                    complexity=TaskComplexity.MODERATE
                )
        
        # Analyze keywords and context
        vision_score = self._calculate_vision_score(task_lower, has_dom_state)
        
        # Determine final classification
        requires_vision = vision_score > 0.5
        action_type = self._infer_action_type(task_lower)
        complexity = self._infer_complexity(task_lower, requires_vision)
        
        reasoning = self._generate_reasoning(task_lower, vision_score, has_dom_state)
        
        return ActionAnalysis(
            action_type=action_type,
            requires_vision=requires_vision,
            confidence_score=abs(vision_score - 0.5) * 2,  # Convert to 0-1 confidence
            reasoning=reasoning,
            complexity=complexity
        )
    
    def _calculate_vision_score(self, task_lower: str, has_dom_state: bool) -> float:
        """Calculate a score (0-1) indicating likelihood of needing vision."""
        score = 0.5  # Start neutral
        
        # Check for vision-required keywords
        vision_keywords_found = sum(1 for keyword in self._vision_required_keywords 
                                  if keyword in task_lower)
        score += vision_keywords_found * 0.15
        
        # Check for DOM-sufficient keywords
        dom_keywords_found = sum(1 for keyword in self._dom_sufficient_keywords 
                               if keyword in task_lower)
        score -= dom_keywords_found * 0.1
        
        # If we have DOM state, reduce vision requirement for common actions
        if has_dom_state:
            if any(action in task_lower for action in ['click', 'input', 'type', 'fill', 'select']):
                score -= 0.2
        
        # Specific action analysis
        if 'extract' in task_lower and 'structured' in task_lower:
            score -= 0.1  # Structured extraction often works with text
        
        if any(word in task_lower for word in ['find', 'locate', 'identify']):
            score += 0.2
        
        if any(word in task_lower for word in ['blue', 'red', 'green', 'large', 'small']):
            score += 0.3
        
        return max(0.0, min(1.0, score))
    
    def _infer_action_type(self, task_lower: str) -> ActionType:
        """Infer the most likely action type from task description."""
        if any(word in task_lower for word in ['navigate', 'go to', 'visit', 'open']):
            return ActionType.NAVIGATION
        elif any(word in task_lower for word in ['click', 'tap', 'press']):
            return ActionType.FORM_INTERACTION
        elif any(word in task_lower for word in ['type', 'input', 'fill', 'enter']):
            return ActionType.FORM_INTERACTION
        elif any(word in task_lower for word in ['find', 'locate', 'identify', 'look']):
            return ActionType.VISUAL_ANALYSIS
        elif any(word in task_lower for word in ['extract', 'get', 'read']):
            return ActionType.CONTENT_EXTRACTION
        elif any(word in task_lower for word in ['scroll', 'page up', 'page down']):
            return ActionType.SCROLLING
        elif any(word in task_lower for word in ['tab', 'window']):
            return ActionType.TAB_MANAGEMENT
        elif any(word in task_lower for word in ['dropdown', 'select', 'choose']):
            return ActionType.DROPDOWN_INTERACTION
        else:
            return ActionType.ELEMENT_SELECTION
    
    def _infer_complexity(self, task_lower: str, requires_vision: bool) -> TaskComplexity:
        """Infer task complexity."""
        # Multi-step or planning indicators
        if any(word in task_lower for word in ['then', 'after', 'once', 'plan', 'strategy']):
            return TaskComplexity.COMPLEX
        
        # Conditional logic
        if any(word in task_lower for word in ['if', 'when', 'unless', 'depending']):
            return TaskComplexity.MODERATE
        
        # Vision tasks are generally more complex
        if requires_vision:
            return TaskComplexity.MODERATE
        
        return TaskComplexity.SIMPLE
    
    def _generate_reasoning(self, task_lower: str, vision_score: float, has_dom_state: bool) -> str:
        """Generate human-readable reasoning for the classification."""
        reasons = []
        
        if vision_score > 0.7:
            reasons.append("High vision score due to visual element identification requirements")
        elif vision_score < 0.3:
            reasons.append("Low vision score - can likely use DOM structure")
        
        if has_dom_state:
            reasons.append("DOM state available with indexed elements")
        else:
            reasons.append("No DOM state available")
        
        vision_keywords = [k for k in self._vision_required_keywords if k in task_lower]
        if vision_keywords:
            reasons.append(f"Contains vision keywords: {', '.join(vision_keywords[:3])}")
        
        dom_keywords = [k for k in self._dom_sufficient_keywords if k in task_lower]
        if dom_keywords:
            reasons.append(f"Contains DOM keywords: {', '.join(dom_keywords[:3])}")
        
        return "; ".join(reasons) if reasons else "Standard classification based on task content"
    
    def batch_classify(self, tasks: List[str], has_dom_state: bool = False) -> List[ActionAnalysis]:
        """Classify multiple tasks at once."""
        return [self.classify_action(task, has_dom_state) for task in tasks]
    
    def get_stats(self, analyses: List[ActionAnalysis]) -> Dict[str, Any]:
        """Get statistics from a batch of analyses."""
        total = len(analyses)
        if total == 0:
            return {}
        
        vision_required = sum(1 for a in analyses if a.requires_vision)
        
        # Group by action type
        action_type_counts = {}
        for analysis in analyses:
            action_type = analysis.action_type.value
            action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
        
        # Complexity distribution
        complexity_counts = {}
        for analysis in analyses:
            complexity = analysis.complexity.value
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        return {
            'total_tasks': total,
            'vision_required': vision_required,
            'vision_percentage': (vision_required / total) * 100,
            'text_only': total - vision_required,
            'text_only_percentage': ((total - vision_required) / total) * 100,
            'action_types': action_type_counts,
            'complexity_distribution': complexity_counts,
            'average_confidence': sum(a.confidence_score for a in analyses) / total
        }