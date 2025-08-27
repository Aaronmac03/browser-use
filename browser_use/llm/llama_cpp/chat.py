from dataclasses import dataclass
from typing import Any, TypeVar, overload
import json
import httpx
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.llama_cpp.serializer import LlamaCppMessageSerializer
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatLlamaCpp(BaseChatModel):
	"""
	A wrapper around llama.cpp server's chat API for vision models.
	Designed as a drop-in replacement for Ollama integration.
	"""

	model: str

	# Client configuration
	host: str = "http://localhost:8080"
	timeout: float = 60.0
	client_params: dict[str, Any] | None = None

	# Static properties
	@property
	def provider(self) -> str:
		return 'llama_cpp'

	@property
	def name(self) -> str:
		return self.model

	def _get_client_params(self) -> dict[str, Any]:
		"""Prepare client parameters dictionary."""
		return {
			'host': self.host,
			'timeout': self.timeout,
			'client_params': self.client_params,
		}

	def get_client(self) -> httpx.AsyncClient:
		"""Returns an httpx AsyncClient for llama.cpp server communication."""
		return httpx.AsyncClient(timeout=self.timeout)

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		llama_cpp_messages = LlamaCppMessageSerializer.serialize_messages(messages)

		try:
			async with self.get_client() as client:
				# Prepare request payload
				payload = {
					"messages": llama_cpp_messages,
					"temperature": 0.1,
					"max_tokens": 1024,
					"stream": False
				}

				# Add JSON schema for structured output if requested
				if output_format is not None:
					schema = output_format.model_json_schema()
					payload["response_format"] = {
						"type": "json_object",
						"schema": schema
					}

				response = await client.post(
					f"{self.host}/v1/chat/completions",
					json=payload,
					headers={"Content-Type": "application/json"}
				)
				
				response.raise_for_status()
				result = response.json()

				if "choices" not in result or not result["choices"]:
					raise ModelProviderError(message="No response from llama.cpp server", model=self.name)

				content = result["choices"][0]["message"]["content"]

				if output_format is None:
					return ChatInvokeCompletion(completion=content, usage=None)
				else:
					# Parse structured output
					try:
						parsed_content = output_format.model_validate_json(content)
						return ChatInvokeCompletion(completion=parsed_content, usage=None)
					except Exception as e:
						# Fallback: try to parse as JSON and then validate
						try:
							json_data = json.loads(content)
							parsed_content = output_format.model_validate(json_data)
							return ChatInvokeCompletion(completion=parsed_content, usage=None)
						except Exception:
							raise ModelProviderError(
								message=f"Failed to parse structured output: {str(e)}", 
								model=self.name
							) from e

		except httpx.HTTPError as e:
			raise ModelProviderError(message=f"HTTP error: {str(e)}", model=self.name) from e
		except Exception as e:
			raise ModelProviderError(message=str(e), model=self.name) from e