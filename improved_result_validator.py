#!/usr/bin/env python3
"""
Improved Result Validation System
================================

Addresses result validation issues that cause false negatives:
1. Intelligent success criteria evaluation
2. Context-aware validation logic
3. Partial success recognition
4. Timeout vs. actual failure distinction
5. Evidence-based validation with fallbacks
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationResult(Enum):
	"""Result of validation check."""
	SUCCESS = "success"
	PARTIAL_SUCCESS = "partial_success"
	FAILURE = "failure"
	INSUFFICIENT_DATA = "insufficient_data"
	TIMEOUT = "timeout"

@dataclass
class ValidationEvidence:
	"""Evidence collected for validation."""
	url: Optional[str] = None
	title: Optional[str] = None
	page_text: Optional[str] = None
	dom_elements: List[str] = None
	screenshots: List[str] = None
	execution_time: float = 0.0
	actions_taken: List[str] = None
	errors_encountered: List[str] = None
	
	def __post_init__(self):
		if self.dom_elements is None:
			self.dom_elements = []
		if self.screenshots is None:
			self.screenshots = []
		if self.actions_taken is None:
			self.actions_taken = []
		if self.errors_encountered is None:
			self.errors_encountered = []

@dataclass
class ValidationCriteria:
	"""Criteria for validating task success."""
	task_description: str
	success_indicators: List[str]
	failure_indicators: List[str]
	required_url_patterns: List[str] = None
	required_page_elements: List[str] = None
	timeout_threshold: float = 240.0
	partial_success_threshold: float = 0.6
	
	def __post_init__(self):
		if self.required_url_patterns is None:
			self.required_url_patterns = []
		if self.required_page_elements is None:
			self.required_page_elements = []

class ImprovedResultValidator:
	"""
	Intelligent result validation system.
	
	Key improvements:
	- Multi-dimensional validation (URL, content, actions, time)
	- Partial success recognition
	- Context-aware criteria interpretation
	- Evidence-based decision making
	- Fallback validation strategies
	"""
	
	def __init__(self):
		self.validation_history = []
		self.success_patterns = {}
		self.failure_patterns = {}
	
	def validate_task_result(
		self,
		criteria: ValidationCriteria,
		evidence: ValidationEvidence,
		agent_result: Optional[Dict[str, Any]] = None
	) -> Tuple[ValidationResult, Dict[str, Any]]:
		"""
		Validate task result using multiple validation strategies.
		
		Args:
			criteria: Validation criteria for the task
			evidence: Evidence collected during execution
			agent_result: Result reported by the agent
			
		Returns:
			(ValidationResult, detailed_analysis)
		"""
		logger.info(f"[VALIDATOR] Validating task: {criteria.task_description[:50]}...")
		
		analysis = {
			'validation_result': ValidationResult.FAILURE,
			'confidence_score': 0.0,
			'evidence_summary': {},
			'validation_checks': {},
			'recommendations': []
		}
		
		try:
			# Step 1: Check for timeout
			if evidence.execution_time > criteria.timeout_threshold:
				analysis['validation_result'] = ValidationResult.TIMEOUT
				analysis['recommendations'].append("Consider increasing timeout or simplifying task")
				return ValidationResult.TIMEOUT, analysis
			
			# Step 2: Collect validation evidence
			evidence_summary = self._analyze_evidence(evidence, criteria)
			analysis['evidence_summary'] = evidence_summary
			
			# Step 3: Run validation checks
			validation_checks = self._run_validation_checks(criteria, evidence, agent_result)
			analysis['validation_checks'] = validation_checks
			
			# Step 4: Calculate confidence score
			confidence_score = self._calculate_confidence_score(validation_checks, evidence_summary)
			analysis['confidence_score'] = confidence_score
			
			# Step 5: Determine final result
			final_result = self._determine_final_result(confidence_score, validation_checks, criteria)
			analysis['validation_result'] = final_result
			
			# Step 6: Generate recommendations
			recommendations = self._generate_recommendations(final_result, validation_checks, evidence_summary)
			analysis['recommendations'] = recommendations
			
			# Step 7: Update validation history
			self._update_validation_history(criteria, evidence, final_result, confidence_score)
			
			logger.info(f"[VALIDATOR] Result: {final_result.value} (confidence: {confidence_score:.2f})")
			return final_result, analysis
			
		except Exception as e:
			logger.error(f"[VALIDATOR] Validation error: {e}")
			analysis['validation_result'] = ValidationResult.INSUFFICIENT_DATA
			analysis['recommendations'].append(f"Validation failed due to error: {e}")
			return ValidationResult.INSUFFICIENT_DATA, analysis
	
	def _analyze_evidence(self, evidence: ValidationEvidence, criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Analyze collected evidence for validation."""
		summary = {
			'url_analysis': self._analyze_url(evidence.url, criteria),
			'content_analysis': self._analyze_content(evidence.page_text, evidence.title, criteria),
			'action_analysis': self._analyze_actions(evidence.actions_taken, criteria),
			'error_analysis': self._analyze_errors(evidence.errors_encountered),
			'timing_analysis': self._analyze_timing(evidence.execution_time, criteria)
		}
		
		return summary
	
	def _analyze_url(self, url: Optional[str], criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Analyze URL evidence."""
		analysis = {
			'current_url': url,
			'url_relevant': False,
			'matches_required_patterns': False,
			'url_score': 0.0
		}
		
		if not url:
			return analysis
		
		url_lower = url.lower()
		
		# Check against required URL patterns
		if criteria.required_url_patterns:
			for pattern in criteria.required_url_patterns:
				if re.search(pattern.lower(), url_lower):
					analysis['matches_required_patterns'] = True
					analysis['url_score'] += 0.3
					break
		
		# Check relevance to task description
		task_keywords = self._extract_keywords(criteria.task_description)
		for keyword in task_keywords:
			if keyword.lower() in url_lower:
				analysis['url_relevant'] = True
				analysis['url_score'] += 0.2
		
		# Check against success indicators
		for indicator in criteria.success_indicators:
			if indicator.lower() in url_lower:
				analysis['url_score'] += 0.3
		
		analysis['url_score'] = min(analysis['url_score'], 1.0)
		return analysis
	
	def _analyze_content(self, page_text: Optional[str], title: Optional[str], criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Analyze page content evidence."""
		analysis = {
			'has_content': bool(page_text),
			'title_relevant': False,
			'content_matches_indicators': 0,
			'content_score': 0.0,
			'matched_indicators': []
		}
		
		if not page_text and not title:
			return analysis
		
		# Combine text sources
		combined_text = ""
		if page_text:
			combined_text += page_text.lower()
		if title:
			combined_text += " " + title.lower()
			analysis['title_relevant'] = any(
				keyword.lower() in title.lower() 
				for keyword in self._extract_keywords(criteria.task_description)
			)
		
		# Check success indicators
		for indicator in criteria.success_indicators:
			if indicator.lower() in combined_text:
				analysis['content_matches_indicators'] += 1
				analysis['matched_indicators'].append(indicator)
				analysis['content_score'] += 0.2
		
		# Check failure indicators (negative score)
		for failure_indicator in criteria.failure_indicators:
			if failure_indicator.lower() in combined_text:
				analysis['content_score'] -= 0.3
		
		# Bonus for having substantial content
		if page_text and len(page_text) > 100:
			analysis['content_score'] += 0.1
		
		analysis['content_score'] = max(0.0, min(analysis['content_score'], 1.0))
		return analysis
	
	def _analyze_actions(self, actions: List[str], criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Analyze actions taken during execution."""
		analysis = {
			'actions_count': len(actions),
			'has_navigation': False,
			'has_interaction': False,
			'has_completion': False,
			'action_score': 0.0
		}
		
		if not actions:
			return analysis
		
		# Analyze action types
		for action in actions:
			action_lower = action.lower()
			
			if any(nav_word in action_lower for nav_word in ['navigate', 'go_to', 'url']):
				analysis['has_navigation'] = True
				analysis['action_score'] += 0.2
			
			if any(interact_word in action_lower for interact_word in ['click', 'type', 'scroll', 'select']):
				analysis['has_interaction'] = True
				analysis['action_score'] += 0.2
			
			if any(complete_word in action_lower for complete_word in ['done', 'complete', 'finish']):
				analysis['has_completion'] = True
				analysis['action_score'] += 0.3
		
		# Bonus for reasonable action count (not too few, not too many)
		if 1 <= len(actions) <= 10:
			analysis['action_score'] += 0.2
		elif len(actions) > 20:
			analysis['action_score'] -= 0.1  # Penalty for excessive actions
		
		analysis['action_score'] = max(0.0, min(analysis['action_score'], 1.0))
		return analysis
	
	def _analyze_errors(self, errors: List[str]) -> Dict[str, Any]:
		"""Analyze errors encountered during execution."""
		analysis = {
			'error_count': len(errors),
			'has_critical_errors': False,
			'has_recoverable_errors': False,
			'error_score': 1.0  # Start with perfect score, deduct for errors
		}
		
		if not errors:
			return analysis
		
		critical_error_patterns = [
			'timeout', 'connection', 'crash', 'fatal', 'critical'
		]
		
		recoverable_error_patterns = [
			'element not found', 'retry', 'warning', 'minor'
		]
		
		for error in errors:
			error_lower = error.lower()
			
			if any(pattern in error_lower for pattern in critical_error_patterns):
				analysis['has_critical_errors'] = True
				analysis['error_score'] -= 0.4
			elif any(pattern in error_lower for pattern in recoverable_error_patterns):
				analysis['has_recoverable_errors'] = True
				analysis['error_score'] -= 0.1
			else:
				analysis['error_score'] -= 0.2  # Unknown error
		
		analysis['error_score'] = max(0.0, analysis['error_score'])
		return analysis
	
	def _analyze_timing(self, execution_time: float, criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Analyze execution timing."""
		analysis = {
			'execution_time': execution_time,
			'within_timeout': execution_time <= criteria.timeout_threshold,
			'reasonable_duration': False,
			'timing_score': 0.0
		}
		
		# Reasonable duration is between 5 seconds and 80% of timeout
		reasonable_min = 5.0
		reasonable_max = criteria.timeout_threshold * 0.8
		
		if reasonable_min <= execution_time <= reasonable_max:
			analysis['reasonable_duration'] = True
			analysis['timing_score'] = 1.0
		elif execution_time < reasonable_min:
			# Too fast might indicate incomplete execution
			analysis['timing_score'] = 0.5
		elif execution_time > reasonable_max:
			# Too slow but within timeout
			analysis['timing_score'] = 0.3
		else:
			# Over timeout
			analysis['timing_score'] = 0.0
		
		return analysis
	
	def _run_validation_checks(
		self,
		criteria: ValidationCriteria,
		evidence: ValidationEvidence,
		agent_result: Optional[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""Run comprehensive validation checks."""
		checks = {}
		
		# Check 1: Agent self-reported success
		checks['agent_success'] = self._check_agent_success(agent_result)
		
		# Check 2: URL validation
		checks['url_validation'] = self._check_url_requirements(evidence.url, criteria)
		
		# Check 3: Content validation
		checks['content_validation'] = self._check_content_requirements(
			evidence.page_text, evidence.title, criteria
		)
		
		# Check 4: Action sequence validation
		checks['action_validation'] = self._check_action_sequence(evidence.actions_taken, criteria)
		
		# Check 5: Error threshold validation
		checks['error_validation'] = self._check_error_threshold(evidence.errors_encountered)
		
		# Check 6: Timing validation
		checks['timing_validation'] = self._check_timing_requirements(evidence.execution_time, criteria)
		
		return checks
	
	def _check_agent_success(self, agent_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
		"""Check agent's self-reported success."""
		check = {
			'passed': False,
			'confidence': 0.0,
			'details': 'No agent result provided'
		}
		
		if agent_result:
			if agent_result.get('success', False):
				check['passed'] = True
				check['confidence'] = 0.7  # Moderate confidence in self-report
				check['details'] = 'Agent reported success'
			else:
				check['details'] = f"Agent reported failure: {agent_result.get('error', 'Unknown error')}"
		
		return check
	
	def _check_url_requirements(self, url: Optional[str], criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Check URL-based requirements."""
		check = {
			'passed': True,  # Default to pass if no requirements
			'confidence': 1.0,
			'details': 'No URL requirements specified'
		}
		
		if criteria.required_url_patterns and url:
			url_lower = url.lower()
			matched_patterns = []
			
			for pattern in criteria.required_url_patterns:
				if re.search(pattern.lower(), url_lower):
					matched_patterns.append(pattern)
			
			if matched_patterns:
				check['passed'] = True
				check['confidence'] = 0.8
				check['details'] = f"URL matches required patterns: {matched_patterns}"
			else:
				check['passed'] = False
				check['confidence'] = 0.9
				check['details'] = f"URL '{url}' does not match required patterns: {criteria.required_url_patterns}"
		
		return check
	
	def _check_content_requirements(
		self,
		page_text: Optional[str],
		title: Optional[str],
		criteria: ValidationCriteria
	) -> Dict[str, Any]:
		"""Check content-based requirements."""
		check = {
			'passed': False,
			'confidence': 0.0,
			'details': 'No content available for validation'
		}
		
		if not page_text and not title:
			return check
		
		combined_text = ""
		if page_text:
			combined_text += page_text.lower()
		if title:
			combined_text += " " + title.lower()
		
		# Check success indicators
		matched_indicators = []
		for indicator in criteria.success_indicators:
			if indicator.lower() in combined_text:
				matched_indicators.append(indicator)
		
		# Check failure indicators
		matched_failures = []
		for failure_indicator in criteria.failure_indicators:
			if failure_indicator.lower() in combined_text:
				matched_failures.append(failure_indicator)
		
		# Determine result
		if matched_failures:
			check['passed'] = False
			check['confidence'] = 0.8
			check['details'] = f"Content contains failure indicators: {matched_failures}"
		elif matched_indicators:
			success_ratio = len(matched_indicators) / len(criteria.success_indicators)
			check['passed'] = success_ratio >= 0.5  # At least half of indicators
			check['confidence'] = min(0.9, 0.5 + success_ratio * 0.4)
			check['details'] = f"Content matches {len(matched_indicators)}/{len(criteria.success_indicators)} success indicators: {matched_indicators}"
		else:
			check['passed'] = False
			check['confidence'] = 0.6
			check['details'] = "Content does not contain expected success indicators"
		
		return check
	
	def _check_action_sequence(self, actions: List[str], criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Check if action sequence is reasonable."""
		check = {
			'passed': True,
			'confidence': 0.7,
			'details': f"Executed {len(actions)} actions"
		}
		
		if not actions:
			check['passed'] = False
			check['confidence'] = 0.9
			check['details'] = "No actions were executed"
		elif len(actions) > 50:
			check['passed'] = False
			check['confidence'] = 0.8
			check['details'] = f"Too many actions executed ({len(actions)}), possible infinite loop"
		
		return check
	
	def _check_error_threshold(self, errors: List[str]) -> Dict[str, Any]:
		"""Check if error count is within acceptable threshold."""
		check = {
			'passed': True,
			'confidence': 1.0,
			'details': f"Encountered {len(errors)} errors"
		}
		
		if len(errors) > 10:
			check['passed'] = False
			check['confidence'] = 0.9
			check['details'] = f"Too many errors encountered ({len(errors)})"
		elif len(errors) > 5:
			check['confidence'] = 0.7
			check['details'] = f"Moderate number of errors ({len(errors)}), but within threshold"
		
		return check
	
	def _check_timing_requirements(self, execution_time: float, criteria: ValidationCriteria) -> Dict[str, Any]:
		"""Check timing requirements."""
		check = {
			'passed': execution_time <= criteria.timeout_threshold,
			'confidence': 1.0,
			'details': f"Execution time: {execution_time:.1f}s (timeout: {criteria.timeout_threshold}s)"
		}
		
		if execution_time > criteria.timeout_threshold:
			check['confidence'] = 0.95
			check['details'] = f"Execution exceeded timeout: {execution_time:.1f}s > {criteria.timeout_threshold}s"
		
		return check
	
	def _calculate_confidence_score(
		self,
		validation_checks: Dict[str, Any],
		evidence_summary: Dict[str, Any]
	) -> float:
		"""Calculate overall confidence score."""
		scores = []
		weights = []
		
		# Weight validation checks
		for check_name, check_result in validation_checks.items():
			if check_result['passed']:
				scores.append(check_result['confidence'])
			else:
				scores.append(0.0)
			
			# Different weights for different checks
			if check_name == 'content_validation':
				weights.append(0.3)
			elif check_name == 'agent_success':
				weights.append(0.2)
			elif check_name == 'url_validation':
				weights.append(0.2)
			else:
				weights.append(0.1)
		
		# Add evidence scores
		for evidence_type, evidence_data in evidence_summary.items():
			if isinstance(evidence_data, dict) and 'score' in evidence_data:
				scores.append(evidence_data['score'])
				weights.append(0.05)  # Lower weight for evidence
		
		# Calculate weighted average
		if scores and weights:
			weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
			total_weight = sum(weights)
			return weighted_sum / total_weight if total_weight > 0 else 0.0
		
		return 0.0
	
	def _determine_final_result(
		self,
		confidence_score: float,
		validation_checks: Dict[str, Any],
		criteria: ValidationCriteria
	) -> ValidationResult:
		"""Determine final validation result."""
		# Check for critical failures first
		if not validation_checks.get('timing_validation', {}).get('passed', True):
			return ValidationResult.TIMEOUT
		
		if not validation_checks.get('error_validation', {}).get('passed', True):
			return ValidationResult.FAILURE
		
		# Use confidence score for main determination
		if confidence_score >= 0.8:
			return ValidationResult.SUCCESS
		elif confidence_score >= criteria.partial_success_threshold:
			return ValidationResult.PARTIAL_SUCCESS
		elif confidence_score >= 0.3:
			return ValidationResult.INSUFFICIENT_DATA
		else:
			return ValidationResult.FAILURE
	
	def _generate_recommendations(
		self,
		result: ValidationResult,
		validation_checks: Dict[str, Any],
		evidence_summary: Dict[str, Any]
	) -> List[str]:
		"""Generate recommendations based on validation results."""
		recommendations = []
		
		if result == ValidationResult.FAILURE:
			recommendations.append("Task failed - consider breaking into smaller subtasks")
			
			# Specific recommendations based on failed checks
			if not validation_checks.get('content_validation', {}).get('passed', True):
				recommendations.append("Content validation failed - verify success indicators are appropriate")
			
			if not validation_checks.get('url_validation', {}).get('passed', True):
				recommendations.append("URL validation failed - check navigation logic")
			
			if not validation_checks.get('action_validation', {}).get('passed', True):
				recommendations.append("Action sequence issues - review action planning")
		
		elif result == ValidationResult.PARTIAL_SUCCESS:
			recommendations.append("Partial success achieved - consider refining approach")
			recommendations.append("Review success criteria to ensure they're not too strict")
		
		elif result == ValidationResult.TIMEOUT:
			recommendations.append("Task timed out - consider increasing timeout or simplifying")
			recommendations.append("Break complex tasks into smaller, faster subtasks")
		
		elif result == ValidationResult.INSUFFICIENT_DATA:
			recommendations.append("Insufficient data for validation - improve evidence collection")
			recommendations.append("Ensure proper page content extraction and action logging")
		
		return recommendations
	
	def _extract_keywords(self, text: str) -> List[str]:
		"""Extract keywords from text."""
		# Simple keyword extraction - can be enhanced
		words = re.findall(r'\b\w{3,}\b', text.lower())
		# Filter out common words
		stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'will', 'with'}
		return [word for word in words if word not in stop_words][:10]  # Top 10 keywords
	
	def _update_validation_history(
		self,
		criteria: ValidationCriteria,
		evidence: ValidationEvidence,
		result: ValidationResult,
		confidence: float
	):
		"""Update validation history for learning."""
		history_entry = {
			'task_description': criteria.task_description,
			'result': result,
			'confidence': confidence,
			'timestamp': evidence.execution_time,
			'url': evidence.url,
			'actions_count': len(evidence.actions_taken),
			'errors_count': len(evidence.errors_encountered)
		}
		
		self.validation_history.append(history_entry)
		
		# Keep only recent history
		if len(self.validation_history) > 100:
			self.validation_history = self.validation_history[-100:]
	
	def get_validation_stats(self) -> Dict[str, Any]:
		"""Get validation statistics."""
		if not self.validation_history:
			return {'total_validations': 0}
		
		total = len(self.validation_history)
		success_count = sum(1 for entry in self.validation_history if entry['result'] == ValidationResult.SUCCESS)
		partial_count = sum(1 for entry in self.validation_history if entry['result'] == ValidationResult.PARTIAL_SUCCESS)
		
		avg_confidence = sum(entry['confidence'] for entry in self.validation_history) / total
		
		return {
			'total_validations': total,
			'success_rate': success_count / total,
			'partial_success_rate': partial_count / total,
			'average_confidence': avg_confidence,
			'recent_results': [entry['result'].value for entry in self.validation_history[-10:]]
		}


# Usage helper functions
def create_validation_criteria(
	task_description: str,
	success_indicators: List[str],
	failure_indicators: List[str] = None,
	timeout: float = 240.0
) -> ValidationCriteria:
	"""Create validation criteria for a task."""
	return ValidationCriteria(
		task_description=task_description,
		success_indicators=success_indicators,
		failure_indicators=failure_indicators or [],
		timeout_threshold=timeout
	)

def create_validation_evidence(
	url: str = None,
	title: str = None,
	page_text: str = None,
	actions: List[str] = None,
	errors: List[str] = None,
	execution_time: float = 0.0
) -> ValidationEvidence:
	"""Create validation evidence from execution data."""
	return ValidationEvidence(
		url=url,
		title=title,
		page_text=page_text,
		actions_taken=actions or [],
		errors_encountered=errors or [],
		execution_time=execution_time
	)