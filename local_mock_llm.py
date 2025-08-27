#!/usr/bin/env python3
"""
Local mock LLM that implements ChatOllama-compatible interface for testing
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, TypeVar, overload
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel  
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=BaseModel)

@dataclass  
class ChatLocalMock(BaseChatModel):
	"""
	A local mock that behaves like ChatOllama but doesn't need external services
	"""
	
	model: str = "local-mock"
	
	@property
	def provider(self) -> str:
		return 'local-mock'
	
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
		
		# Simulate processing time (very fast)
		await asyncio.sleep(0.05)
		
		# Get the last message content
		last_message_content = str(messages[-1].content) if messages else ""
		
		try:
			if output_format is None:
				# Return simple text response
				response = self._generate_text_response(last_message_content)
				return ChatInvokeCompletion(completion=response, usage=None)
			else:
				# Return structured response
				response_dict = self._generate_structured_response(last_message_content, output_format)
				response_json = json.dumps(response_dict)
				completion = output_format.model_validate_json(response_json)
				return ChatInvokeCompletion(completion=completion, usage=None)
				
		except Exception as e:
			from browser_use.llm.exceptions import ModelProviderError
			raise ModelProviderError(message=str(e), model=self.name) from e
	
	def _generate_text_response(self, prompt: str) -> str:
		"""Generate appropriate text response based on prompt content"""
		prompt_lower = prompt.lower()
		
		if "screenshot" in prompt_lower or "image" in prompt_lower:
			return "I can see a web page with various interactive elements including buttons, links, and text fields."
		elif "action" in prompt_lower or "click" in prompt_lower:
			return "I should click on the most relevant interactive element to proceed."
		elif "navigate" in prompt_lower or "go to" in prompt_lower:
			return "I will navigate to the requested location."
		else:
			return "I understand the task and will proceed accordingly."
	
	def _generate_structured_response(self, prompt: str, output_format: type[BaseModel]) -> dict[str, Any]:
		"""Generate structured response matching the expected schema"""
		
		# Get schema to understand expected structure
		schema = output_format.model_json_schema()
		properties = schema.get('properties', {})
		
		response = {}
		
		# Handle common browser automation fields
		if 'action' in properties:
			response['action'] = 'click'
		if 'coordinate' in properties:  
			response['coordinate'] = [300, 400]
		if 'text' in properties:
			response['text'] = 'clickable element'
		if 'confidence' in properties:
			response['confidence'] = 0.85
		if 'reasoning' in properties:
			response['reasoning'] = 'Selected most appropriate element based on context'
		if 'description' in properties:
			response['description'] = 'Interactive web element suitable for the requested action'
		if 'elements' in properties:
			response['elements'] = ['button', 'link', 'input']
		if 'success' in properties:
			response['success'] = True
		if 'message' in properties:
			response['message'] = 'Action completed successfully'
		
		# Fill in any remaining required fields with defaults
		for field_name, field_info in properties.items():
			if field_name not in response:
				if field_info.get('type') == 'string':
					response[field_name] = 'default_value'
				elif field_info.get('type') == 'number':
					response[field_name] = 0.5
				elif field_info.get('type') == 'integer':
					response[field_name] = 1
				elif field_info.get('type') == 'boolean':
					response[field_name] = True
				elif field_info.get('type') == 'array':
					response[field_name] = []
		
		return response


async def test_local_mock():
	"""Test the local mock LLM"""
	print("Testing Local Mock LLM...")
	
	from browser_use.llm.messages import UserMessage
	
	llm = ChatLocalMock(model="test-mock")
	
	# Test text response
	messages = [UserMessage(content="What do you see in this screenshot?")]
	response1 = await llm.ainvoke(messages)
	print(f"Text response: {response1.completion}")
	
	# Test with a simple structured output (we'll need to define a simple model)
	from pydantic import BaseModel
	
	class SimpleAction(BaseModel):
		action: str
		confidence: float
		reasoning: str
	
	response2 = await llm.ainvoke(messages, output_format=SimpleAction)
	print(f"Structured response: {response2.completion}")
	
	print("[SUCCESS] Local mock LLM is working!")
	return True

if __name__ == "__main__":
	success = asyncio.run(test_local_mock())