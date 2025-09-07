#!/usr/bin/env python3
"""
Improved Schema Transformation System
====================================

Addresses schema compatibility issues between local LLM output and browser-use expectations:
1. Robust transformation of 'actions' array to 'action' field
2. Parameter extraction and flattening
3. Missing parameter injection with sensible defaults
4. Model class name normalization
5. Fallback parsing for edge cases
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SchemaTransformationResult:
	"""Result of schema transformation operation."""
	success: bool
	transformed_data: Optional[Dict[str, Any]]
	original_data: Optional[Dict[str, Any]]
	transformations_applied: List[str]
	errors: List[str]

class ImprovedSchemaHandler:
	"""
	Robust schema transformation system for local LLM outputs.
	
	Handles common issues:
	- actions[] -> action field conversion
	- Double-nested parameters
	- Missing required parameters
	- Model class name issues
	- Malformed JSON recovery
	"""
	
	def __init__(self):
		self.transformation_stats = {
			'total_processed': 0,
			'successful_transforms': 0,
			'failed_transforms': 0,
			'transformation_types': {}
		}
	
	def transform_llm_output(self, raw_output: str) -> SchemaTransformationResult:
		"""
		Transform raw LLM output to browser-use compatible format.
		
		Args:
			raw_output: Raw JSON string from LLM
			
		Returns:
			SchemaTransformationResult with transformation details
		"""
		self.transformation_stats['total_processed'] += 1
		
		result = SchemaTransformationResult(
			success=False,
			transformed_data=None,
			original_data=None,
			transformations_applied=[],
			errors=[]
		)
		
		try:
			# Step 1: Extract and parse JSON
			json_data = self._extract_and_parse_json(raw_output)
			if not json_data:
				result.errors.append("Could not extract valid JSON from output")
				return result
			
			result.original_data = json_data.copy()
			
			# Step 2: Apply transformations
			transformed_data = json_data.copy()
			
			# Transform actions array to action field
			if self._has_actions_array(transformed_data):
				transformed_data = self._transform_actions_array(transformed_data)
				result.transformations_applied.append("actions_array_to_action_field")
			
			# Extract and flatten double-nested parameters
			if self._has_nested_parameters(transformed_data):
				transformed_data = self._flatten_nested_parameters(transformed_data)
				result.transformations_applied.append("flatten_nested_parameters")
			
			# Inject missing required parameters
			missing_params = self._find_missing_parameters(transformed_data)
			if missing_params:
				transformed_data = self._inject_missing_parameters(transformed_data, missing_params)
				result.transformations_applied.append("inject_missing_parameters")
			
			# Normalize model class names
			if self._has_model_class_names(transformed_data):
				transformed_data = self._normalize_model_class_names(transformed_data)
				result.transformations_applied.append("normalize_model_class_names")
			
			# Validate final structure
			if self._validate_transformed_structure(transformed_data):
				result.success = True
				result.transformed_data = transformed_data
				self.transformation_stats['successful_transforms'] += 1
				
				# Update transformation type stats
				for transform_type in result.transformations_applied:
					self.transformation_stats['transformation_types'][transform_type] = \
						self.transformation_stats['transformation_types'].get(transform_type, 0) + 1
			else:
				result.errors.append("Transformed structure failed validation")
				self.transformation_stats['failed_transforms'] += 1
		
		except Exception as e:
			result.errors.append(f"Transformation failed: {str(e)}")
			self.transformation_stats['failed_transforms'] += 1
			logger.error(f"[SCHEMA] Transformation error: {e}")
		
		return result
	
	def _extract_and_parse_json(self, raw_output: str) -> Optional[Dict[str, Any]]:
		"""Extract and parse JSON from raw LLM output."""
		try:
			# First, try direct parsing
			return json.loads(raw_output.strip())
		except json.JSONDecodeError:
			pass
		
		# Try to find JSON within the text
		json_patterns = [
			r'\{.*\}',  # Basic JSON object
			r'```json\s*(\{.*?\})\s*```',  # JSON in code blocks
			r'```\s*(\{.*?\})\s*```',  # JSON in generic code blocks
		]
		
		for pattern in json_patterns:
			matches = re.findall(pattern, raw_output, re.DOTALL)
			for match in matches:
				try:
					return json.loads(match)
				except json.JSONDecodeError:
					continue
		
		# Try to extract from the first { to last }
		start = raw_output.find('{')
		end = raw_output.rfind('}')
		if start != -1 and end != -1 and end > start:
			try:
				return json.loads(raw_output[start:end+1])
			except json.JSONDecodeError:
				pass
		
		return None
	
	def _has_actions_array(self, data: Dict[str, Any]) -> bool:
		"""Check if data has 'actions' array instead of 'action' field."""
		return 'actions' in data and isinstance(data['actions'], list)
	
	def _transform_actions_array(self, data: Dict[str, Any]) -> Dict[str, Any]:
		"""Transform 'actions' array to 'action' field."""
		transformed = data.copy()
		
		if 'actions' in transformed and isinstance(transformed['actions'], list):
			actions = transformed['actions']
			
			if len(actions) == 1:
				# Single action - convert to action field
				action = actions[0]
				if isinstance(action, dict):
					# Extract action type and parameters
					if 'action' in action and 'params' in action:
						# Format: {"action": "name", "params": {...}}
						action_name = action['action']
						params = action['params']
						transformed['action'] = [{action_name: params}]
					elif len(action) == 1:
						# Format: {"action_name": {...}}
						transformed['action'] = [action]
					else:
						# Complex action object
						transformed['action'] = [action]
				
				# Remove original actions array
				del transformed['actions']
			
			elif len(actions) > 1:
				# Multiple actions - keep as array but rename
				transformed['action'] = actions
				del transformed['actions']
		
		return transformed
	
	def _has_nested_parameters(self, data: Dict[str, Any]) -> bool:
		"""Check if data has double-nested parameters."""
		if 'action' not in data:
			return False
		
		action = data['action']
		if isinstance(action, list) and len(action) > 0:
			first_action = action[0]
			if isinstance(first_action, dict):
				for action_name, params in first_action.items():
					if isinstance(params, dict) and action_name in params:
						return True
		
		return False
	
	def _flatten_nested_parameters(self, data: Dict[str, Any]) -> Dict[str, Any]:
		"""Flatten double-nested parameters."""
		transformed = data.copy()
		
		if 'action' in transformed and isinstance(transformed['action'], list):
			flattened_actions = []
			
			for action in transformed['action']:
				if isinstance(action, dict):
					flattened_action = {}
					for action_name, params in action.items():
						if isinstance(params, dict) and action_name in params:
							# Double-nested: {"action_name": {"action_name": {...}}}
							flattened_action[action_name] = params[action_name]
						else:
							# Normal: {"action_name": {...}}
							flattened_action[action_name] = params
					flattened_actions.append(flattened_action)
				else:
					flattened_actions.append(action)
			
			transformed['action'] = flattened_actions
		
		return transformed
	
	def _find_missing_parameters(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
		"""Find missing required parameters for actions."""
		missing_params = {}
		
		# Define required parameters for common actions
		required_params = {
			'extract_structured_data': {'extract_links': False},
			'click_element': {},
			'type_text': {},
			'navigate_to_url': {},
			'scroll': {},
			'done': {}
		}
		
		if 'action' in data and isinstance(data['action'], list):
			for i, action in enumerate(data['action']):
				if isinstance(action, dict):
					for action_name, params in action.items():
						if action_name in required_params:
							required = required_params[action_name]
							if isinstance(params, dict):
								for req_param, default_value in required.items():
									if req_param not in params:
										if action_name not in missing_params:
											missing_params[action_name] = {}
										missing_params[action_name][req_param] = default_value
		
		return missing_params
	
	def _inject_missing_parameters(self, data: Dict[str, Any], missing_params: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
		"""Inject missing required parameters with defaults."""
		transformed = data.copy()
		
		if 'action' in transformed and isinstance(transformed['action'], list):
			for i, action in enumerate(transformed['action']):
				if isinstance(action, dict):
					for action_name, params in action.items():
						if action_name in missing_params:
							if isinstance(params, dict):
								for param_name, default_value in missing_params[action_name].items():
									if param_name not in params:
										params[param_name] = default_value
		
		return transformed
	
	def _has_model_class_names(self, data: Dict[str, Any]) -> bool:
		"""Check if data has model class names instead of action names."""
		if 'action' not in data:
			return False
		
		action = data['action']
		if isinstance(action, list) and len(action) > 0:
			first_action = action[0]
			if isinstance(first_action, dict):
				for action_name in first_action.keys():
					if self._is_model_class_name(action_name):
						return True
		
		return False
	
	def _is_model_class_name(self, name: str) -> bool:
		"""Check if name looks like a model class name."""
		# Model class names typically end with "ActionModel" or "Action"
		return (name.endswith('ActionModel') or 
				(name.endswith('Action') and name[0].isupper()) or
				re.match(r'^[A-Z][a-zA-Z]*ActionModel$', name) or
				re.match(r'^[A-Z][a-zA-Z]*Action$', name))
	
	def _normalize_model_class_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
		"""Convert model class names to snake_case action names."""
		transformed = data.copy()
		
		if 'action' in transformed and isinstance(transformed['action'], list):
			normalized_actions = []
			
			for action in transformed['action']:
				if isinstance(action, dict):
					normalized_action = {}
					for action_name, params in action.items():
						if self._is_model_class_name(action_name):
							# Convert CamelCase to snake_case
							snake_case_name = self._camel_to_snake(action_name)
							# Remove "ActionModel" or "Action" suffix
							snake_case_name = re.sub(r'_action(_model)?$', '', snake_case_name)
							normalized_action[snake_case_name] = params
						else:
							normalized_action[action_name] = params
					normalized_actions.append(normalized_action)
				else:
					normalized_actions.append(action)
			
			transformed['action'] = normalized_actions
		
		return transformed
	
	def _camel_to_snake(self, name: str) -> str:
		"""Convert CamelCase to snake_case."""
		# Insert underscore before uppercase letters (except first)
		s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
		# Insert underscore before uppercase letters preceded by lowercase
		return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
	
	def _validate_transformed_structure(self, data: Dict[str, Any]) -> bool:
		"""Validate that transformed data has correct structure."""
		try:
			# Must have either 'action' field or be a valid response
			if 'action' not in data and 'thinking' not in data:
				return False
			
			# If has action, it should be a list
			if 'action' in data:
				if not isinstance(data['action'], list):
					return False
				
				# Each action should be a dict with one key-value pair
				for action in data['action']:
					if not isinstance(action, dict):
						return False
					if len(action) != 1:
						return False
			
			return True
		
		except Exception:
			return False
	
	def get_transformation_stats(self) -> Dict[str, Any]:
		"""Get statistics about transformations performed."""
		total = self.transformation_stats['total_processed']
		success_rate = (self.transformation_stats['successful_transforms'] / total * 100) if total > 0 else 0
		
		return {
			'total_processed': total,
			'successful_transforms': self.transformation_stats['successful_transforms'],
			'failed_transforms': self.transformation_stats['failed_transforms'],
			'success_rate': f"{success_rate:.1f}%",
			'transformation_types': self.transformation_stats['transformation_types']
		}


class SchemaValidationHelper:
	"""
	Helper class for validating schema transformations.
	"""
	
	@staticmethod
	def validate_browser_use_format(data: Dict[str, Any]) -> tuple[bool, List[str]]:
		"""
		Validate that data conforms to browser-use expected format.
		
		Returns:
			(is_valid, list_of_issues)
		"""
		issues = []
		
		# Check for required structure
		if not isinstance(data, dict):
			issues.append("Data must be a dictionary")
			return False, issues
		
		# Check action field format
		if 'action' in data:
			action = data['action']
			if not isinstance(action, list):
				issues.append("'action' field must be a list")
			else:
				for i, act in enumerate(action):
					if not isinstance(act, dict):
						issues.append(f"Action {i} must be a dictionary")
					elif len(act) != 1:
						issues.append(f"Action {i} must have exactly one key-value pair")
		
		# Check for common required fields in specific actions
		if 'action' in data and isinstance(data['action'], list):
			for action in data['action']:
				if isinstance(action, dict):
					for action_name, params in action.items():
						validation_issues = SchemaValidationHelper._validate_action_params(action_name, params)
						issues.extend(validation_issues)
		
		return len(issues) == 0, issues
	
	@staticmethod
	def _validate_action_params(action_name: str, params: Any) -> List[str]:
		"""Validate parameters for specific action types."""
		issues = []
		
		# Define validation rules for common actions
		validation_rules = {
			'done': {
				'required_fields': ['text', 'success'],
				'field_types': {'text': str, 'success': bool}
			},
			'click_element': {
				'required_fields': ['element_id'],
				'field_types': {'element_id': (str, int)}
			},
			'type_text': {
				'required_fields': ['text'],
				'field_types': {'text': str}
			},
			'navigate_to_url': {
				'required_fields': ['url'],
				'field_types': {'url': str}
			}
		}
		
		if action_name in validation_rules:
			rules = validation_rules[action_name]
			
			if not isinstance(params, dict):
				issues.append(f"{action_name} parameters must be a dictionary")
				return issues
			
			# Check required fields
			for field in rules.get('required_fields', []):
				if field not in params:
					issues.append(f"{action_name} missing required field: {field}")
			
			# Check field types
			for field, expected_type in rules.get('field_types', {}).items():
				if field in params:
					if not isinstance(params[field], expected_type):
						issues.append(f"{action_name}.{field} should be {expected_type.__name__}")
		
		return issues


# Usage example and integration helper
def create_schema_handler() -> ImprovedSchemaHandler:
	"""Factory function to create schema handler."""
	return ImprovedSchemaHandler()

def transform_llm_response(raw_response: str) -> Dict[str, Any]:
	"""
	Simple interface for transforming LLM responses.
	
	Args:
		raw_response: Raw JSON string from LLM
		
	Returns:
		Transformed data ready for browser-use
		
	Raises:
		ValueError: If transformation fails
	"""
	handler = ImprovedSchemaHandler()
	result = handler.transform_llm_output(raw_response)
	
	if result.success:
		logger.info(f"[SCHEMA] Applied transformations: {', '.join(result.transformations_applied)}")
		return result.transformed_data
	else:
		error_msg = f"Schema transformation failed: {'; '.join(result.errors)}"
		logger.error(f"[SCHEMA] {error_msg}")
		raise ValueError(error_msg)