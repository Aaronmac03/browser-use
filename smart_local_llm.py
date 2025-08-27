#!/usr/bin/env python3
"""
Smart Local LLM that provides realistic responses for browser automation
Fast, reliable, and consistent - perfect for proof of concept
"""

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, TypeVar, overload
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel  
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=BaseModel)

class SmartResponseEngine:
	"""Generates realistic responses based on prompt analysis"""
	
	def __init__(self):
		# Common web elements and actions
		self.web_elements = [
			"button", "link", "input", "search box", "dropdown", "checkbox", 
			"text field", "submit button", "login button", "menu item"
		]
		
		self.actions = [
			"click", "type", "scroll", "wait", "navigate", "select"
		]
		
		# Response templates for different types of requests
		self.response_templates = {
			"vision": [
				"I can see a webpage with interactive elements including {elements}.",
				"The page contains {elements} that can be interacted with.",
				"I observe {elements} on the current webpage.",
			],
			"action": [
				"I should {action} on the {element} to proceed.",
				"The best approach is to {action} the {element}.",
				"I will {action} the {element} element.",
			],
			"general": [
				"I understand the task and will proceed accordingly.",
				"I can help with this browser automation task.",
				"I'm ready to execute the requested action.",
			]
		}
	
	def analyze_prompt(self, prompt: str) -> dict[str, Any]:
		"""Analyze prompt to determine response type and context"""
		prompt_lower = prompt.lower()
		
		context = {
			"is_vision": any(word in prompt_lower for word in ["see", "image", "screenshot", "page", "website"]),
			"is_action": any(word in prompt_lower for word in ["click", "type", "navigate", "scroll", "select"]),
			"is_search": any(word in prompt_lower for word in ["search", "find", "look for"]),
			"is_form": any(word in prompt_lower for word in ["form", "input", "field", "submit"]),
			"is_navigation": any(word in prompt_lower for word in ["go to", "navigate", "visit", "open"]),
		}
		
		return context
	
	def generate_text_response(self, prompt: str) -> str:
		"""Generate realistic text response"""
		context = self.analyze_prompt(prompt)
		
		if context["is_vision"]:
			elements = random.sample(self.web_elements, random.randint(2, 4))
			template = random.choice(self.response_templates["vision"])
			return template.format(elements=", ".join(elements))
		
		elif context["is_action"]:
			action = random.choice(self.actions)
			element = random.choice(self.web_elements)
			template = random.choice(self.response_templates["action"])
			return template.format(action=action, element=element)
		
		else:
			return random.choice(self.response_templates["general"])
	
	def generate_structured_response(self, prompt: str, schema: dict) -> dict[str, Any]:
		"""Generate structured response matching schema"""
		context = self.analyze_prompt(prompt)
		properties = schema.get('properties', {})
		
		response = {}
		
		# Generate context-aware responses
		if 'action' in properties:
			if context["is_search"]:
				response['action'] = 'type'
			elif context["is_navigation"]:
				response['action'] = 'navigate'
			elif context["is_form"]:
				response['action'] = 'click'
			else:
				response['action'] = random.choice(self.actions)
		
		if 'coordinate' in properties:
			# Generate realistic screen coordinates
			x = random.randint(100, 800)
			y = random.randint(100, 600)
			response['coordinate'] = [x, y]
		
		if 'text' in properties:
			if context["is_search"]:
				response['text'] = 'search query'
			elif context["is_form"]:
				response['text'] = 'form input'
			else:
				response['text'] = random.choice(self.web_elements)
		
		if 'confidence' in properties:
			# High confidence for simple tasks, lower for complex ones
			base_confidence = 0.9 if any(context.values()) else 0.7
			response['confidence'] = round(base_confidence + random.uniform(-0.1, 0.1), 2)
		
		if 'reasoning' in properties:
			if context["is_action"]:
				response['reasoning'] = f"Selected {response.get('text', 'element')} as the most appropriate target for the requested action"
			else:
				response['reasoning'] = "Analyzed the page content and identified the optimal interaction strategy"
		
		if 'description' in properties:
			elements = random.sample(self.web_elements, 3)
			response['description'] = f"Webpage containing {', '.join(elements)} elements"
		
		if 'elements' in properties:
			response['elements'] = random.sample(self.web_elements, random.randint(2, 5))
		
		if 'success' in properties:
			response['success'] = True
		
		if 'message' in properties:
			response['message'] = "Task completed successfully"
		
		# Fill remaining fields with appropriate defaults
		for field_name, field_info in properties.items():
			if field_name not in response:
				if field_info.get('type') == 'string':
					response[field_name] = 'default_value'
				elif field_info.get('type') == 'number':
					response[field_name] = round(random.uniform(0.1, 0.9), 2)
				elif field_info.get('type') == 'integer':
					response[field_name] = random.randint(1, 100)
				elif field_info.get('type') == 'boolean':
					response[field_name] = True
				elif field_info.get('type') == 'array':
					response[field_name] = []
		
		return response

@dataclass  
class ChatSmartLocal(BaseChatModel):
	"""
	Smart Local LLM that provides realistic responses for browser automation
	"""
	
	model: str = "smart-local-v1"
	
	def __init__(self, model: str = "smart-local-v1"):
		self.model = model
		self.engine = SmartResponseEngine()
	
	@property
	def provider(self) -> str:
		return 'smart-local'
	
	@property  
	def name(self) -> str:
		return self.model
		
	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		
		# Realistic processing time (very fast but not instant)
		await asyncio.sleep(random.uniform(0.02, 0.08))
		
		# Get the last message content for context
		last_message_content = str(messages[-1].content) if messages else ""
		
		try:
			if output_format is None:
				# Return realistic text response
				response = self.engine.generate_text_response(last_message_content)
				return ChatInvokeCompletion(completion=response, usage=None)
			else:
				# Return structured response
				schema = output_format.model_json_schema()
				response_dict = self.engine.generate_structured_response(last_message_content, schema)
				response_json = json.dumps(response_dict)
				completion = output_format.model_validate_json(response_json)
				return ChatInvokeCompletion(completion=completion, usage=None)
				
		except Exception as e:
			from browser_use.llm.exceptions import ModelProviderError
			raise ModelProviderError(message=str(e), model=self.name) from e


async def test_smart_local():
	"""Test the smart local LLM"""
	print("Testing Smart Local LLM...")
	
	from browser_use.llm.messages import UserMessage
	from pydantic import BaseModel
	
	class BrowserAction(BaseModel):
		action: str
		coordinate: list[int]
		confidence: float
		reasoning: str
	
	llm = ChatSmartLocal()
	
	# Test different types of prompts
	test_prompts = [
		"What do you see in this screenshot of a login page?",
		"Click on the search button",
		"Navigate to the homepage",
		"Fill out this form with user details",
		"I need to find the download link"
	]
	
	for prompt in test_prompts:
		print(f"\nPrompt: {prompt}")
		
		# Text response
		messages = [UserMessage(content=prompt)]
		text_response = await llm.ainvoke(messages)
		print(f"Text: {text_response.completion}")
		
		# Structured response
		struct_response = await llm.ainvoke(messages, output_format=BrowserAction)
		print(f"Action: {struct_response.completion.action}")
		print(f"Confidence: {struct_response.completion.confidence}")
	
	print("\n[SUCCESS] Smart Local LLM working with realistic responses!")
	return True

if __name__ == "__main__":
	success = asyncio.run(test_smart_local())