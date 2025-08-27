#!/usr/bin/env python3
"""
Advanced Task Success Validation System
Goes beyond URL pattern matching to validate task completion through multiple criteria
"""

import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class ValidationCriteria(Enum):
	"""Types of validation criteria."""
	URL_PATTERN = "url_pattern"
	CONTENT_PRESENCE = "content_presence"
	PRICE_EXTRACTION = "price_extraction"
	FORM_COMPLETION = "form_completion"
	AVAILABILITY_CHECK = "availability_check"
	STRUCTURED_DATA = "structured_data"
	VISUAL_CONFIRMATION = "visual_confirmation"
	SUCCESS_MESSAGE = "success_message"
	ERROR_ABSENCE = "error_absence"


@dataclass
class ValidationRule:
	"""Individual validation rule."""
	criteria: ValidationCriteria
	pattern: str
	weight: float = 1.0
	required: bool = False
	description: str = ""


@dataclass
class ValidationResult:
	"""Result of a validation check."""
	rule: ValidationRule
	passed: bool
	confidence: float
	extracted_data: Optional[Dict[str, Any]] = None
	details: str = ""


@dataclass
class TaskValidation:
	"""Complete task validation results."""
	task_description: str
	overall_success: bool
	confidence_score: float
	validation_results: List[ValidationResult]
	extracted_data: Dict[str, Any]
	recommendation: str


class TaskValidator:
	"""Validates task completion using multiple sophisticated criteria."""
	
	def __init__(self):
		"""Initialize task validator with built-in patterns."""
		self.price_patterns = [
			r'\$[\d,]+\.?\d*',  # $123.45, $1,234
			r'[\d,]+\.?\d*\s*(?:USD|dollars?)',  # 123.45 USD
			r'Price:?\s*\$?[\d,]+\.?\d*',  # Price: $123.45
			r'Total:?\s*\$?[\d,]+\.?\d*',  # Total: $123.45
			r'(\d+\.?\d*)\s*per\s+night',  # 99.50 per night
		]
		
		self.availability_patterns = [
			r'(?:in\s+stock|available|ready)',
			r'(?:out\s+of\s+stock|unavailable|sold\s+out)',
			r'(?:\d+\s+available|\d+\s+in\s+stock)',
			r'(?:book\s+now|reserve|check\s+availability)',
		]
		
		self.success_message_patterns = [
			r'(?:success|successful|confirmed|complete|booked)',
			r'(?:thank\s+you|confirmation)',
			r'(?:order\s+placed|reservation\s+made)',
			r'(?:added\s+to\s+cart|item\s+added)',
		]
		
		self.error_patterns = [
			r'(?:error|failed|failure|problem)',
			r'(?:invalid|incorrect|not\s+found)',
			r'(?:unable\s+to|cannot|can\'t)',
			r'(?:please\s+try\s+again|something\s+went\s+wrong)',
		]
	
	def create_hotel_booking_rules(self, hotel_name: str = "", 
								 check_in: str = "", check_out: str = "") -> List[ValidationRule]:
		"""Create validation rules for hotel booking tasks."""
		rules = [
			# URL-based validation
			ValidationRule(
				criteria=ValidationCriteria.URL_PATTERN,
				pattern=r'(?:booking|reservation|hotel|room)',
				weight=0.5,
				description="URL indicates booking/hotel context"
			),
			
			# Price extraction
			ValidationRule(
				criteria=ValidationCriteria.PRICE_EXTRACTION,
				pattern='|'.join(self.price_patterns),
				weight=2.0,
				required=True,
				description="Extract room price information"
			),
			
			# Availability check
			ValidationRule(
				criteria=ValidationCriteria.AVAILABILITY_CHECK,
				pattern='|'.join(self.availability_patterns),
				weight=1.5,
				required=True,
				description="Verify room availability status"
			),
			
			# Hotel name confirmation
			ValidationRule(
				criteria=ValidationCriteria.CONTENT_PRESENCE,
				pattern=hotel_name.lower() if hotel_name else r'(?:hotel|inn|resort|lodge)',
				weight=1.0,
				description=f"Confirm hotel name: {hotel_name}" if hotel_name else "Detect hotel context"
			),
			
			# Date validation
			ValidationRule(
				criteria=ValidationCriteria.STRUCTURED_DATA,
				pattern=r'(?:check.?in|arrival|from).*?(?:\d{1,2}[/\-]\d{1,2}|\w+\s+\d{1,2})',
				weight=1.0,
				description="Verify check-in date presence"
			),
			
			# Visual confirmation of booking interface
			ValidationRule(
				criteria=ValidationCriteria.VISUAL_CONFIRMATION,
				pattern=r'(?:book|reserve|select|choose)',
				weight=0.8,
				description="Detect booking interface elements"
			),
			
			# Success message detection
			ValidationRule(
				criteria=ValidationCriteria.SUCCESS_MESSAGE,
				pattern='|'.join(self.success_message_patterns),
				weight=1.5,
				description="Detect booking success indicators"
			),
			
			# Error absence
			ValidationRule(
				criteria=ValidationCriteria.ERROR_ABSENCE,
				pattern='|'.join(self.error_patterns),
				weight=1.0,
				description="Ensure no error messages present"
			)
		]
		
		return rules
	
	def create_product_search_rules(self, product_name: str = "") -> List[ValidationRule]:
		"""Create validation rules for product search tasks."""
		rules = [
			# URL validation
			ValidationRule(
				criteria=ValidationCriteria.URL_PATTERN,
				pattern=r'(?:search|product|shop|store)',
				weight=0.5,
				description="URL indicates shopping context"
			),
			
			# Product presence
			ValidationRule(
				criteria=ValidationCriteria.CONTENT_PRESENCE,
				pattern=product_name.lower() if product_name else r'product|item',
				weight=1.5,
				required=True,
				description=f"Find product: {product_name}" if product_name else "Detect products"
			),
			
			# Price extraction
			ValidationRule(
				criteria=ValidationCriteria.PRICE_EXTRACTION,
				pattern='|'.join(self.price_patterns),
				weight=2.0,
				required=True,
				description="Extract product pricing"
			),
			
			# Availability
			ValidationRule(
				criteria=ValidationCriteria.AVAILABILITY_CHECK,
				pattern='|'.join(self.availability_patterns),
				weight=1.5,
				description="Check product availability"
			),
			
			# Add to cart functionality
			ValidationRule(
				criteria=ValidationCriteria.VISUAL_CONFIRMATION,
				pattern=r'(?:add\s+to\s+cart|buy\s+now|purchase|order)',
				weight=1.0,
				description="Detect purchase options"
			)
		]
		
		return rules
	
	def create_form_filling_rules(self, required_fields: List[str] = None) -> List[ValidationRule]:
		"""Create validation rules for form filling tasks."""
		rules = [
			# Form completion
			ValidationRule(
				criteria=ValidationCriteria.FORM_COMPLETION,
				pattern=r'(?:submit|send|continue|next|complete)',
				weight=2.0,
				required=True,
				description="Form submission available"
			),
			
			# Success confirmation
			ValidationRule(
				criteria=ValidationCriteria.SUCCESS_MESSAGE,
				pattern='|'.join(self.success_message_patterns),
				weight=1.5,
				description="Form submission success"
			),
			
			# Error absence
			ValidationRule(
				criteria=ValidationCriteria.ERROR_ABSENCE,
				pattern='|'.join(self.error_patterns),
				weight=1.0,
				description="No form validation errors"
			)
		]
		
		# Add field-specific validation if provided
		if required_fields:
			for field in required_fields:
				rules.append(ValidationRule(
					criteria=ValidationCriteria.STRUCTURED_DATA,
					pattern=field.lower(),
					weight=0.5,
					description=f"Field present: {field}"
				))
		
		return rules
	
	async def validate_url_pattern(self, rule: ValidationRule, url: str) -> ValidationResult:
		"""Validate URL against pattern."""
		try:
			pattern_match = re.search(rule.pattern, url.lower(), re.IGNORECASE)
			passed = pattern_match is not None
			confidence = 1.0 if passed else 0.0
			
			return ValidationResult(
				rule=rule,
				passed=passed,
				confidence=confidence,
				details=f"URL {'matches' if passed else 'does not match'} pattern: {rule.pattern}"
			)
		except Exception as e:
			return ValidationResult(
				rule=rule,
				passed=False,
				confidence=0.0,
				details=f"Pattern validation failed: {e}"
			)
	
	async def validate_content_presence(self, rule: ValidationRule, 
									  page_content: str, vision_state: Dict = None) -> ValidationResult:
		"""Validate content presence in page text and vision analysis."""
		try:
			# Check in page content
			content_match = re.search(rule.pattern, page_content.lower(), re.IGNORECASE)
			
			# Check in vision analysis if available
			vision_match = False
			if vision_state and 'caption' in vision_state:
				vision_match = re.search(rule.pattern, vision_state['caption'].lower(), re.IGNORECASE) is not None
			
			# Check vision elements
			elements_match = False
			if vision_state and 'elements' in vision_state:
				for element in vision_state['elements']:
					if 'visible_text' in element:
						if re.search(rule.pattern, element['visible_text'].lower(), re.IGNORECASE):
							elements_match = True
							break
			
			passed = content_match or vision_match or elements_match
			confidence = 0.8 if content_match else (0.6 if vision_match else (0.4 if elements_match else 0.0))
			
			sources = []
			if content_match:
				sources.append("page content")
			if vision_match:
				sources.append("vision caption")
			if elements_match:
				sources.append("vision elements")
			
			return ValidationResult(
				rule=rule,
				passed=passed,
				confidence=confidence,
				details=f"Pattern found in: {', '.join(sources) if sources else 'none'}"
			)
			
		except Exception as e:
			return ValidationResult(
				rule=rule,
				passed=False,
				confidence=0.0,
				details=f"Content validation failed: {e}"
			)
	
	async def validate_price_extraction(self, rule: ValidationRule, 
									  page_content: str, vision_state: Dict = None) -> ValidationResult:
		"""Extract and validate pricing information."""
		try:
			extracted_prices = []
			
			# Extract from page content
			for pattern in self.price_patterns:
				matches = re.findall(pattern, page_content, re.IGNORECASE)
				extracted_prices.extend(matches)
			
			# Extract from vision state
			if vision_state:
				vision_text = vision_state.get('caption', '') + ' '
				if 'elements' in vision_state:
					for element in vision_state['elements']:
						vision_text += element.get('visible_text', '') + ' '
				
				for pattern in self.price_patterns:
					matches = re.findall(pattern, vision_text, re.IGNORECASE)
					extracted_prices.extend(matches)
			
			# Clean and deduplicate prices
			unique_prices = list(set(extracted_prices))
			
			passed = len(unique_prices) > 0
			confidence = min(1.0, len(unique_prices) * 0.3)  # More prices = higher confidence
			
			return ValidationResult(
				rule=rule,
				passed=passed,
				confidence=confidence,
				extracted_data={'prices': unique_prices},
				details=f"Found {len(unique_prices)} price(s): {', '.join(unique_prices[:3])}"
			)
			
		except Exception as e:
			return ValidationResult(
				rule=rule,
				passed=False,
				confidence=0.0,
				details=f"Price extraction failed: {e}"
			)
	
	async def validate_availability_check(self, rule: ValidationRule, 
										page_content: str, vision_state: Dict = None) -> ValidationResult:
		"""Check availability status indicators."""
		try:
			all_text = page_content.lower()
			if vision_state and 'caption' in vision_state:
				all_text += ' ' + vision_state['caption'].lower()
			
			availability_indicators = []
			for pattern in self.availability_patterns:
				matches = re.findall(pattern, all_text, re.IGNORECASE)
				availability_indicators.extend(matches)
			
			# Determine availability status
			positive_indicators = ['in stock', 'available', 'ready', 'book now', 'reserve']
			negative_indicators = ['out of stock', 'unavailable', 'sold out']
			
			positive_count = sum(1 for indicator in availability_indicators 
							   if any(pos in indicator.lower() for pos in positive_indicators))
			negative_count = sum(1 for indicator in availability_indicators 
							   if any(neg in indicator.lower() for neg in negative_indicators))
			
			# Availability is good if we have positive indicators and few/no negative ones
			passed = positive_count > 0 or (len(availability_indicators) > 0 and negative_count == 0)
			confidence = min(1.0, (positive_count * 0.4) + (len(availability_indicators) * 0.2))
			
			availability_status = "available" if positive_count > negative_count else ("unavailable" if negative_count > 0 else "unknown")
			
			return ValidationResult(
				rule=rule,
				passed=passed,
				confidence=confidence,
				extracted_data={'availability_status': availability_status, 'indicators': availability_indicators},
				details=f"Availability: {availability_status} ({len(availability_indicators)} indicators)"
			)
			
		except Exception as e:
			return ValidationResult(
				rule=rule,
				passed=False,
				confidence=0.0,
				details=f"Availability check failed: {e}"
			)
	
	async def validate_visual_confirmation(self, rule: ValidationRule, 
										 vision_state: Dict = None) -> ValidationResult:
		"""Validate visual elements match expected interface."""
		try:
			if not vision_state:
				return ValidationResult(
					rule=rule,
					passed=False,
					confidence=0.0,
					details="No vision data available"
				)
			
			# Check affordances and elements
			visual_elements = []
			
			if 'affordances' in vision_state:
				for affordance in vision_state['affordances']:
					if 'label' in affordance:
						visual_elements.append(affordance['label'].lower())
			
			if 'elements' in vision_state:
				for element in vision_state['elements']:
					if 'visible_text' in element:
						visual_elements.append(element['visible_text'].lower())
			
			# Check if expected visual patterns are present
			pattern_matches = 0
			for element_text in visual_elements:
				if re.search(rule.pattern, element_text, re.IGNORECASE):
					pattern_matches += 1
			
			passed = pattern_matches > 0
			confidence = min(1.0, pattern_matches * 0.3)
			
			return ValidationResult(
				rule=rule,
				passed=passed,
				confidence=confidence,
				extracted_data={'visual_elements': visual_elements[:5]},  # Limit to first 5
				details=f"Found {pattern_matches} matching visual elements"
			)
			
		except Exception as e:
			return ValidationResult(
				rule=rule,
				passed=False,
				confidence=0.0,
				details=f"Visual confirmation failed: {e}"
			)
	
	async def validate_task(self, task_description: str, url: str, page_content: str,
						  vision_state: Dict = None, validation_rules: List[ValidationRule] = None) -> TaskValidation:
		"""Perform comprehensive task validation."""
		
		# Auto-generate rules if not provided
		if validation_rules is None:
			validation_rules = self._infer_validation_rules(task_description)
		
		validation_results = []
		extracted_data = {}
		
		# Run all validation rules
		for rule in validation_rules:
			try:
				if rule.criteria == ValidationCriteria.URL_PATTERN:
					result = await self.validate_url_pattern(rule, url)
				elif rule.criteria == ValidationCriteria.CONTENT_PRESENCE:
					result = await self.validate_content_presence(rule, page_content, vision_state)
				elif rule.criteria == ValidationCriteria.PRICE_EXTRACTION:
					result = await self.validate_price_extraction(rule, page_content, vision_state)
				elif rule.criteria == ValidationCriteria.AVAILABILITY_CHECK:
					result = await self.validate_availability_check(rule, page_content, vision_state)
				elif rule.criteria == ValidationCriteria.VISUAL_CONFIRMATION:
					result = await self.validate_visual_confirmation(rule, vision_state)
				else:
					# Generic content-based validation
					result = await self.validate_content_presence(rule, page_content, vision_state)
				
				validation_results.append(result)
				
				# Collect extracted data
				if result.extracted_data:
					extracted_data.update(result.extracted_data)
					
			except Exception as e:
				# Create failure result for any validation that throws
				validation_results.append(ValidationResult(
					rule=rule,
					passed=False,
					confidence=0.0,
					details=f"Validation error: {e}"
				))
		
		# Calculate overall success and confidence
		total_weight = sum(rule.weight for rule in validation_rules)
		weighted_score = sum(result.confidence * result.rule.weight 
							for result in validation_results)
		
		confidence_score = weighted_score / total_weight if total_weight > 0 else 0.0
		
		# Check required rules
		required_passed = all(result.passed for result in validation_results 
							if result.rule.required)
		
		overall_success = required_passed and confidence_score >= 0.6
		
		# Generate recommendation
		recommendation = self._generate_recommendation(validation_results, confidence_score, overall_success)
		
		return TaskValidation(
			task_description=task_description,
			overall_success=overall_success,
			confidence_score=confidence_score,
			validation_results=validation_results,
			extracted_data=extracted_data,
			recommendation=recommendation
		)
	
	def _infer_validation_rules(self, task_description: str) -> List[ValidationRule]:
		"""Infer appropriate validation rules from task description."""
		task_lower = task_description.lower()
		
		if any(keyword in task_lower for keyword in ['hotel', 'booking', 'room', 'reservation']):
			# Extract hotel name if mentioned
			hotel_match = re.search(r'(?:at|hotel)\s+([A-Za-z\s]+)', task_description, re.IGNORECASE)
			hotel_name = hotel_match.group(1).strip() if hotel_match else ""
			return self.create_hotel_booking_rules(hotel_name)
		
		elif any(keyword in task_lower for keyword in ['search', 'find', 'product', 'buy', 'purchase']):
			# Extract product name if mentioned  
			product_match = re.search(r'(?:search|find|buy)\s+(?:for\s+)?([A-Za-z\s]+)', task_description, re.IGNORECASE)
			product_name = product_match.group(1).strip() if product_match else ""
			return self.create_product_search_rules(product_name)
		
		elif any(keyword in task_lower for keyword in ['form', 'fill', 'submit', 'register', 'sign up']):
			return self.create_form_filling_rules()
		
		else:
			# Generic validation rules
			return [
				ValidationRule(
					criteria=ValidationCriteria.CONTENT_PRESENCE,
					pattern=r'\w+',  # Any word content
					weight=1.0,
					description="Page contains content"
				),
				ValidationRule(
					criteria=ValidationCriteria.ERROR_ABSENCE,
					pattern='|'.join(self.error_patterns),
					weight=1.0,
					description="No error messages"
				)
			]
	
	def _generate_recommendation(self, validation_results: List[ValidationResult], 
								confidence_score: float, overall_success: bool) -> str:
		"""Generate actionable recommendation based on validation results."""
		if overall_success and confidence_score >= 0.8:
			return "Task completed successfully with high confidence"
		
		elif overall_success:
			return "Task likely completed, but some validation criteria were not fully met"
		
		else:
			failed_required = [r for r in validation_results if r.rule.required and not r.passed]
			failed_high_weight = [r for r in validation_results if r.rule.weight > 1.0 and not r.passed]
			
			if failed_required:
				return f"Task failed - missing required elements: {', '.join(r.rule.description for r in failed_required)}"
			elif failed_high_weight:
				return f"Task partially completed - missing important elements: {', '.join(r.rule.description for r in failed_high_weight)}"
			else:
				return f"Task validation inconclusive (confidence: {confidence_score:.1%})"


async def test_task_validator():
	"""Test the task validation system."""
	validator = TaskValidator()
	
	# Test hotel booking scenario
	task_desc = "check price and availability of a room at the Omni Hotel in Louisville for 9/1/25-9/2/25"
	url = "https://booking.com/hotel/omni-louisville"
	page_content = """
	Omni Louisville Hotel
	Check-in: September 1, 2025
	Check-out: September 2, 2025
	Price: $189.50 per night
	Available - Book now
	"""
	
	vision_state = {
		"caption": "Hotel booking page showing room rates and availability",
		"elements": [
			{"role": "button", "visible_text": "Book Now", "confidence": 0.9},
			{"role": "text", "visible_text": "$189.50", "confidence": 0.8}
		],
		"affordances": [
			{"type": "button", "label": "Reserve Room"}
		]
	}
	
	validation = await validator.validate_task(task_desc, url, page_content, vision_state)
	
	print("=== TASK VALIDATION RESULTS ===")
	print(f"Task: {validation.task_description}")
	print(f"Overall Success: {validation.overall_success}")
	print(f"Confidence Score: {validation.confidence_score:.2f}")
	print(f"Recommendation: {validation.recommendation}")
	print(f"Extracted Data: {validation.extracted_data}")
	
	print("\nValidation Details:")
	for result in validation.validation_results:
		status = "✓" if result.passed else "✗"
		print(f"  {status} {result.rule.description} (confidence: {result.confidence:.2f})")
		if result.details:
			print(f"    {result.details}")


if __name__ == "__main__":
	asyncio.run(test_task_validator())