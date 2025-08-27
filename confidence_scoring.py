#!/usr/bin/env python3
"""
Confidence-Based Completion Scoring System
Provides intelligent scoring for task completion confidence
"""

import asyncio
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import statistics


class ConfidenceComponent(Enum):
	"""Components that contribute to confidence scoring."""
	TASK_VALIDATION = "task_validation"
	STRUCTURED_DATA = "structured_data"  
	VISION_ANALYSIS = "vision_analysis"
	USER_INTENT_MATCH = "user_intent_match"
	ERROR_INDICATORS = "error_indicators"
	SUCCESS_INDICATORS = "success_indicators"
	NAVIGATION_SUCCESS = "navigation_success"
	COMPLETION_TIME = "completion_time"


@dataclass
class ConfidenceMetric:
	"""Individual confidence metric."""
	component: ConfidenceComponent
	score: float  # 0.0 to 1.0
	weight: float = 1.0
	explanation: str = ""
	supporting_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfidenceScore:
	"""Complete confidence assessment for task completion."""
	overall_score: float
	confidence_level: str  # "Low", "Medium", "High", "Very High"
	metrics: List[ConfidenceMetric]
	weighted_score: float
	total_weight: float
	recommendation: str
	completion_probability: float
	risk_factors: List[str] = field(default_factory=list)
	positive_indicators: List[str] = field(default_factory=list)


class ConfidenceScorer:
	"""Calculates confidence scores for task completion."""
	
	def __init__(self):
		"""Initialize confidence scorer with default weights."""
		self.component_weights = {
			ConfidenceComponent.TASK_VALIDATION: 2.5,
			ConfidenceComponent.STRUCTURED_DATA: 2.0,
			ConfidenceComponent.VISION_ANALYSIS: 1.5,
			ConfidenceComponent.USER_INTENT_MATCH: 2.0,
			ConfidenceComponent.ERROR_INDICATORS: 1.8,
			ConfidenceComponent.SUCCESS_INDICATORS: 1.7,
			ConfidenceComponent.NAVIGATION_SUCCESS: 1.2,
			ConfidenceComponent.COMPLETION_TIME: 0.8
		}
		
		# Intent keywords for different task types
		self.intent_keywords = {
			'booking': ['book', 'reserve', 'reservation', 'hotel', 'room', 'stay'],
			'shopping': ['buy', 'purchase', 'cart', 'checkout', 'price', 'product'],
			'search': ['find', 'search', 'look', 'locate', 'discover'],
			'form': ['fill', 'submit', 'complete', 'register', 'sign up'],
			'information': ['check', 'verify', 'confirm', 'status', 'availability']
		}
	
	def calculate_task_validation_score(self, validation_result: Dict[str, Any]) -> ConfidenceMetric:
		"""Calculate confidence from task validation results."""
		if not validation_result:
			return ConfidenceMetric(
				component=ConfidenceComponent.TASK_VALIDATION,
				score=0.0,
				explanation="No validation data available"
			)
		
		overall_success = validation_result.get('overall_success', False)
		confidence_score = validation_result.get('confidence_score', 0.0)
		validation_results = validation_result.get('validation_results', [])
		
		# Calculate score based on validation results
		if overall_success:
			base_score = 0.8
		else:
			base_score = 0.3
		
		# Adjust based on confidence score from validation
		adjusted_score = (base_score + confidence_score) / 2
		
		# Bonus for multiple successful validations
		passed_validations = sum(1 for r in validation_results if r.get('passed', False))
		total_validations = len(validation_results)
		
		if total_validations > 0:
			validation_ratio = passed_validations / total_validations
			adjusted_score = adjusted_score * (0.5 + validation_ratio * 0.5)
		
		explanation = f"Task validation: {passed_validations}/{total_validations} rules passed"
		if overall_success:
			explanation += " (overall success)"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.TASK_VALIDATION,
			score=min(1.0, adjusted_score),
			explanation=explanation,
			supporting_data={
				'overall_success': overall_success,
				'validation_score': confidence_score,
				'passed_rules': passed_validations,
				'total_rules': total_validations
			}
		)
	
	def calculate_structured_data_score(self, extraction_result: Dict[str, Any]) -> ConfidenceMetric:
		"""Calculate confidence from structured data extraction."""
		if not extraction_result:
			return ConfidenceMetric(
				component=ConfidenceComponent.STRUCTURED_DATA,
				score=0.0,
				explanation="No structured data available"
			)
		
		extracted_items = extraction_result.get('extracted_items', [])
		summary = extraction_result.get('summary', {})
		
		if not extracted_items:
			return ConfidenceMetric(
				component=ConfidenceComponent.STRUCTURED_DATA,
				score=0.1,
				explanation="No structured data extracted"
			)
		
		# Calculate score based on quantity and quality of extracted data
		high_confidence_items = summary.get('high_confidence_items', 0)
		total_items = summary.get('total_items', 0)
		
		if total_items == 0:
			base_score = 0.1
		else:
			# Score based on proportion of high-confidence items
			high_confidence_ratio = high_confidence_items / total_items
			base_score = 0.3 + (high_confidence_ratio * 0.5)
			
			# Bonus for diverse data types
			data_types = len(summary.get('by_type', {}))
			diversity_bonus = min(0.2, data_types * 0.05)
			base_score += diversity_bonus
		
		# Check for critical data types (prices, availability, dates)
		critical_types = ['price', 'availability', 'date']
		found_critical = sum(1 for t in critical_types if t in summary.get('by_type', {}))
		critical_bonus = found_critical * 0.1
		
		final_score = min(1.0, base_score + critical_bonus)
		
		explanation = f"Extracted {total_items} items ({high_confidence_items} high confidence)"
		if found_critical:
			explanation += f", {found_critical} critical types"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.STRUCTURED_DATA,
			score=final_score,
			explanation=explanation,
			supporting_data={
				'total_items': total_items,
				'high_confidence_items': high_confidence_items,
				'data_types': list(summary.get('by_type', {}).keys()),
				'critical_types_found': found_critical
			}
		)
	
	def calculate_vision_analysis_score(self, vision_state: Dict[str, Any]) -> ConfidenceMetric:
		"""Calculate confidence from vision analysis quality."""
		if not vision_state:
			return ConfidenceMetric(
				component=ConfidenceComponent.VISION_ANALYSIS,
				score=0.0,
				explanation="No vision analysis available"
			)
		
		meta = vision_state.get('meta', {})
		vision_confidence = meta.get('confidence', 0.0)
		processing_time = meta.get('processing_time', float('inf'))
		
		elements = vision_state.get('elements', [])
		affordances = vision_state.get('affordances', [])
		caption = vision_state.get('caption', '')
		
		# Base score from vision model confidence
		base_score = vision_confidence
		
		# Adjust based on richness of analysis
		element_count = len(elements)
		affordance_count = len(affordances)
		caption_quality = min(1.0, len(caption) / 100.0) if caption else 0.0
		
		richness_score = (
			min(0.3, element_count * 0.05) +
			min(0.3, affordance_count * 0.1) +
			caption_quality * 0.2
		)
		
		# Processing time factor (faster is better, but not too fast)
		if 1.0 <= processing_time <= 10.0:
			time_factor = 1.0
		elif processing_time < 1.0:
			time_factor = 0.8  # Suspiciously fast
		else:
			time_factor = max(0.5, 10.0 / processing_time)
		
		final_score = (base_score + richness_score) * time_factor
		final_score = min(1.0, final_score)
		
		explanation = f"Vision confidence: {vision_confidence:.2f}, {element_count} elements, {affordance_count} affordances"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.VISION_ANALYSIS,
			score=final_score,
			explanation=explanation,
			supporting_data={
				'vision_confidence': vision_confidence,
				'elements_count': element_count,
				'affordances_count': affordance_count,
				'processing_time': processing_time
			}
		)
	
	def calculate_user_intent_match(self, task_description: str, 
								  extracted_data: Dict[str, Any],
								  page_content: str = "") -> ConfidenceMetric:
		"""Calculate how well the results match user intent."""
		if not task_description:
			return ConfidenceMetric(
				component=ConfidenceComponent.USER_INTENT_MATCH,
				score=0.5,
				explanation="No task description provided"
			)
		
		task_lower = task_description.lower()
		
		# Identify intent category
		intent_category = None
		intent_score = 0.0
		
		for category, keywords in self.intent_keywords.items():
			keyword_matches = sum(1 for kw in keywords if kw in task_lower)
			if keyword_matches > 0:
				intent_category = category
				intent_score = min(1.0, keyword_matches / len(keywords))
				break
		
		if not intent_category:
			intent_category = "general"
			intent_score = 0.5
		
		# Check if extracted data matches intent
		data_match_score = 0.0
		
		if intent_category == "booking" and extracted_data:
			# Look for hotel/booking related data
			has_price = any("price" in str(item).lower() for item in extracted_data.get('extracted_items', []))
			has_dates = any("date" in str(item).lower() for item in extracted_data.get('extracted_items', []))
			has_availability = any("availability" in str(item).lower() for item in extracted_data.get('extracted_items', []))
			
			data_match_score = (has_price * 0.4 + has_dates * 0.3 + has_availability * 0.3)
		
		elif intent_category == "shopping" and extracted_data:
			# Look for shopping related data
			has_price = any("price" in str(item).lower() for item in extracted_data.get('extracted_items', []))
			has_availability = any("availability" in str(item).lower() for item in extracted_data.get('extracted_items', []))
			
			data_match_score = (has_price * 0.6 + has_availability * 0.4)
		
		elif intent_category == "information" and extracted_data:
			# Any structured data extraction counts
			item_count = len(extracted_data.get('extracted_items', []))
			data_match_score = min(1.0, item_count * 0.2)
		
		else:
			# Generic match - any data is good
			if extracted_data and extracted_data.get('extracted_items'):
				data_match_score = 0.6
		
		# Content relevance check
		content_relevance = 0.0
		if page_content:
			task_keywords = task_description.lower().split()
			content_lower = page_content.lower()
			
			matching_keywords = sum(1 for kw in task_keywords if kw in content_lower and len(kw) > 2)
			content_relevance = min(1.0, matching_keywords / max(len(task_keywords), 1))
		
		# Combine scores
		final_score = (intent_score * 0.4 + data_match_score * 0.4 + content_relevance * 0.2)
		
		explanation = f"Intent: {intent_category}, data match: {data_match_score:.2f}, content relevance: {content_relevance:.2f}"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.USER_INTENT_MATCH,
			score=final_score,
			explanation=explanation,
			supporting_data={
				'intent_category': intent_category,
				'data_match_score': data_match_score,
				'content_relevance': content_relevance
			}
		)
	
	def calculate_error_indicators_score(self, page_content: str = "", 
									   vision_state: Dict[str, Any] = None) -> ConfidenceMetric:
		"""Calculate confidence penalty from error indicators."""
		error_patterns = [
			r'(?i)error',
			r'(?i)failed',
			r'(?i)not found',
			r'(?i)invalid',
			r'(?i)unable to',
			r'(?i)something went wrong',
			r'(?i)please try again',
			r'(?i)404',
			r'(?i)500',
			r'(?i)timeout'
		]
		
		all_text = page_content.lower()
		if vision_state and 'caption' in vision_state:
			all_text += ' ' + vision_state['caption'].lower()
		
		error_count = 0
		found_errors = []
		
		import re
		for pattern in error_patterns:
			matches = re.findall(pattern, all_text)
			error_count += len(matches)
			found_errors.extend(matches[:3])  # Limit examples
		
		# Score decreases with more errors
		if error_count == 0:
			score = 1.0
		elif error_count <= 2:
			score = 0.8
		elif error_count <= 5:
			score = 0.5
		else:
			score = 0.2
		
		explanation = f"Found {error_count} error indicators"
		if found_errors:
			explanation += f": {', '.join(found_errors[:3])}"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.ERROR_INDICATORS,
			score=score,
			explanation=explanation,
			supporting_data={'error_count': error_count, 'errors': found_errors}
		)
	
	def calculate_success_indicators_score(self, page_content: str = "",
										 vision_state: Dict[str, Any] = None) -> ConfidenceMetric:
		"""Calculate confidence boost from success indicators."""
		success_patterns = [
			r'(?i)success',
			r'(?i)confirmed',
			r'(?i)completed',
			r'(?i)thank you',
			r'(?i)congratulations',
			r'(?i)reservation confirmed',
			r'(?i)order placed',
			r'(?i)booking confirmed',
			r'(?i)added to cart',
			r'(?i)checkout'
		]
		
		all_text = page_content.lower()
		if vision_state and 'caption' in vision_state:
			all_text += ' ' + vision_state['caption'].lower()
		
		success_count = 0
		found_successes = []
		
		import re
		for pattern in success_patterns:
			matches = re.findall(pattern, all_text)
			success_count += len(matches)
			found_successes.extend(matches[:3])
		
		# Score increases with success indicators
		score = min(1.0, 0.3 + success_count * 0.2)
		
		explanation = f"Found {success_count} success indicators"
		if found_successes:
			explanation += f": {', '.join(found_successes[:3])}"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.SUCCESS_INDICATORS,
			score=score,
			explanation=explanation,
			supporting_data={'success_count': success_count, 'successes': found_successes}
		)
	
	def calculate_navigation_success_score(self, url: str, task_description: str) -> ConfidenceMetric:
		"""Calculate confidence from navigation success."""
		if not url or not task_description:
			return ConfidenceMetric(
				component=ConfidenceComponent.NAVIGATION_SUCCESS,
				score=0.5,
				explanation="Limited navigation data"
			)
		
		task_lower = task_description.lower()
		url_lower = url.lower()
		
		# Look for task-relevant URL components
		navigation_score = 0.5  # Base score
		
		# Check for relevant domains/paths
		if any(keyword in url_lower for keyword in ['booking', 'reservation', 'hotel']):
			if any(keyword in task_lower for keyword in ['book', 'hotel', 'room']):
				navigation_score += 0.3
		
		if any(keyword in url_lower for keyword in ['shop', 'store', 'cart', 'checkout']):
			if any(keyword in task_lower for keyword in ['buy', 'purchase', 'shop']):
				navigation_score += 0.3
		
		# Penalize error pages
		if any(error in url_lower for error in ['404', '500', 'error', 'not-found']):
			navigation_score -= 0.4
		
		navigation_score = max(0.0, min(1.0, navigation_score))
		
		explanation = f"URL relevance to task"
		if navigation_score > 0.7:
			explanation += " (good match)"
		elif navigation_score < 0.4:
			explanation += " (poor match)"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.NAVIGATION_SUCCESS,
			score=navigation_score,
			explanation=explanation,
			supporting_data={'url': url}
		)
	
	def calculate_completion_time_score(self, completion_time: float, 
									  task_complexity: str = "medium") -> ConfidenceMetric:
		"""Calculate confidence based on task completion time."""
		# Expected time ranges by complexity
		time_ranges = {
			"simple": (5, 30),    # 5-30 seconds
			"medium": (20, 120),  # 20 seconds - 2 minutes  
			"complex": (60, 300)  # 1-5 minutes
		}
		
		expected_min, expected_max = time_ranges.get(task_complexity, (20, 120))
		
		if expected_min <= completion_time <= expected_max:
			score = 1.0
		elif completion_time < expected_min:
			# Too fast might indicate failure
			score = max(0.3, completion_time / expected_min)
		else:
			# Too slow might indicate problems
			score = max(0.2, expected_max / completion_time)
		
		explanation = f"Completion time: {completion_time:.1f}s (expected: {expected_min}-{expected_max}s)"
		
		return ConfidenceMetric(
			component=ConfidenceComponent.COMPLETION_TIME,
			score=score,
			explanation=explanation,
			supporting_data={'completion_time': completion_time, 'expected_range': (expected_min, expected_max)}
		)
	
	async def calculate_confidence_score(self, 
										task_description: str,
										url: str = "",
										page_content: str = "",
										vision_state: Dict[str, Any] = None,
										validation_result: Dict[str, Any] = None,
										extraction_result: Dict[str, Any] = None,
										completion_time: float = 0.0,
										task_complexity: str = "medium") -> ConfidenceScore:
		"""Calculate comprehensive confidence score."""
		
		metrics = []
		
		# Calculate individual metrics
		if validation_result:
			metrics.append(self.calculate_task_validation_score(validation_result))
		
		if extraction_result:
			metrics.append(self.calculate_structured_data_score(extraction_result))
		
		if vision_state:
			metrics.append(self.calculate_vision_analysis_score(vision_state))
		
		metrics.append(self.calculate_user_intent_match(task_description, extraction_result or {}, page_content))
		metrics.append(self.calculate_error_indicators_score(page_content, vision_state))
		metrics.append(self.calculate_success_indicators_score(page_content, vision_state))
		metrics.append(self.calculate_navigation_success_score(url, task_description))
		
		if completion_time > 0:
			metrics.append(self.calculate_completion_time_score(completion_time, task_complexity))
		
		# Calculate weighted score
		total_weighted = 0.0
		total_weight = 0.0
		
		for metric in metrics:
			weight = self.component_weights.get(metric.component, 1.0)
			metric.weight = weight
			total_weighted += metric.score * weight
			total_weight += weight
		
		weighted_score = total_weighted / total_weight if total_weight > 0 else 0.0
		
		# Apply sigmoid function for more nuanced scoring
		overall_score = 1 / (1 + math.exp(-5 * (weighted_score - 0.5)))
		
		# Determine confidence level
		if overall_score >= 0.85:
			confidence_level = "Very High"
		elif overall_score >= 0.70:
			confidence_level = "High"
		elif overall_score >= 0.50:
			confidence_level = "Medium"
		else:
			confidence_level = "Low"
		
		# Calculate completion probability
		completion_probability = overall_score
		
		# Extract risk factors and positive indicators
		risk_factors = [m.explanation for m in metrics if m.score < 0.5]
		positive_indicators = [m.explanation for m in metrics if m.score > 0.8]
		
		# Generate recommendation
		recommendation = self._generate_recommendation(overall_score, metrics)
		
		return ConfidenceScore(
			overall_score=overall_score,
			confidence_level=confidence_level,
			metrics=metrics,
			weighted_score=weighted_score,
			total_weight=total_weight,
			recommendation=recommendation,
			completion_probability=completion_probability,
			risk_factors=risk_factors,
			positive_indicators=positive_indicators
		)
	
	def _generate_recommendation(self, overall_score: float, metrics: List[ConfidenceMetric]) -> str:
		"""Generate recommendation based on confidence analysis."""
		if overall_score >= 0.85:
			return "Task appears to have completed successfully with high confidence"
		elif overall_score >= 0.70:
			return "Task likely completed successfully, minor validation issues"
		elif overall_score >= 0.50:
			lowest_scoring = min(metrics, key=lambda m: m.score)
			return f"Uncertain completion - investigate {lowest_scoring.component.value} issues"
		else:
			failed_metrics = [m for m in metrics if m.score < 0.4]
			if len(failed_metrics) > 1:
				return f"Task likely failed - multiple issues detected in {', '.join(m.component.value for m in failed_metrics[:2])}"
			else:
				return "Task completion confidence is low - manual review recommended"
	
	def print_confidence_report(self, confidence: ConfidenceScore):
		"""Print formatted confidence report."""
		print("\n" + "="*60)
		print("CONFIDENCE SCORING REPORT")
		print("="*60)
		print(f"Overall Score: {confidence.overall_score:.3f}")
		print(f"Confidence Level: {confidence.confidence_level}")
		print(f"Completion Probability: {confidence.completion_probability:.1%}")
		print(f"Recommendation: {confidence.recommendation}")
		
		print(f"\nComponent Scores:")
		print("-" * 60)
		for metric in sorted(confidence.metrics, key=lambda m: m.score, reverse=True):
			score_bar = "█" * int(metric.score * 10) + "░" * (10 - int(metric.score * 10))
			print(f"{metric.component.value:20} {score_bar} {metric.score:.3f} (weight: {metric.weight:.1f})")
			print(f"{'':22} {metric.explanation}")
			print()
		
		if confidence.positive_indicators:
			print("Positive Indicators:")
			for indicator in confidence.positive_indicators[:3]:
				print(f"  ✓ {indicator}")
		
		if confidence.risk_factors:
			print(f"\nRisk Factors:")
			for factor in confidence.risk_factors[:3]:
				print(f"  ⚠ {factor}")
		
		print("="*60)


async def test_confidence_scoring():
	"""Test the confidence scoring system."""
	scorer = ConfidenceScorer()
	
	# Mock data for testing
	task_description = "check price and availability of a room at the Omni Hotel in Louisville for 9/1/25-9/2/25"
	url = "https://booking.com/hotel/omni-louisville"
	page_content = "Omni Louisville Hotel - $189.50 per night - Available for September 1-2, 2025"
	
	vision_state = {
		"caption": "Hotel booking page with pricing and availability",
		"elements": [{"visible_text": "$189.50", "confidence": 0.9}],
		"meta": {"confidence": 0.8, "processing_time": 2.5}
	}
	
	validation_result = {
		"overall_success": True,
		"confidence_score": 0.85,
		"validation_results": [
			{"passed": True, "confidence": 0.9},
			{"passed": True, "confidence": 0.8}
		]
	}
	
	extraction_result = {
		"extracted_items": [
			{"data_type": "price", "confidence": 0.9},
			{"data_type": "availability", "confidence": 0.8}
		],
		"summary": {"total_items": 2, "high_confidence_items": 2, "by_type": {"price": 1, "availability": 1}}
	}
	
	confidence = await scorer.calculate_confidence_score(
		task_description=task_description,
		url=url,
		page_content=page_content,
		vision_state=vision_state,
		validation_result=validation_result,
		extraction_result=extraction_result,
		completion_time=45.0
	)
	
	scorer.print_confidence_report(confidence)


if __name__ == "__main__":
	asyncio.run(test_confidence_scoring())