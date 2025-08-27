import base64
import json
from typing import Any

from browser_use.llm.messages import (
	AssistantMessage,
	BaseMessage,
	SystemMessage,
	ToolCall,
	UserMessage,
)


class LlamaCppMessageSerializer:
	"""Serializer for converting between browser_use message types and llama.cpp server message format."""

	@staticmethod
	def _extract_text_content(content: Any) -> str:
		"""Extract text content from message content, ignoring images."""
		if content is None:
			return ''
		if isinstance(content, str):
			return content

		text_parts: list[str] = []
		for part in content:
			if hasattr(part, 'type'):
				if part.type == 'text':
					text_parts.append(part.text)
				elif part.type == 'refusal':
					text_parts.append(f'[Refusal] {part.refusal}')
			# Skip image parts as they're handled separately

		return '\n'.join(text_parts)

	@staticmethod
	def _extract_images_as_data_urls(content: Any) -> list[str]:
		"""Extract images from message content and return as data URLs."""
		if content is None or isinstance(content, str):
			return []

		images: list[str] = []
		for part in content:
			if hasattr(part, 'type') and part.type == 'image_url':
				url = part.image_url.url
				if url.startswith('data:'):
					# Already a data URL
					images.append(url)
				else:
					# For non-data URLs, we'll need to fetch and convert
					# For now, pass through (llama.cpp server may handle URL loading)
					images.append(url)

		return images

	@staticmethod
	def _create_multimodal_content(text_content: str, images: list[str]) -> list[dict[str, Any]]:
		"""Create multimodal content array for llama.cpp server."""
		content_parts = []
		
		# Add text content if present
		if text_content:
			content_parts.append({
				"type": "text",
				"text": text_content
			})
		
		# Add image content
		for image_url in images:
			content_parts.append({
				"type": "image_url",
				"image_url": {
					"url": image_url
				}
			})
		
		return content_parts

	@staticmethod
	def serialize(message: BaseMessage) -> dict[str, Any]:
		"""Serialize a browser_use message to llama.cpp server message format."""

		if isinstance(message, UserMessage):
			text_content = LlamaCppMessageSerializer._extract_text_content(message.content)
			images = LlamaCppMessageSerializer._extract_images_as_data_urls(message.content)

			if images:
				# Multimodal message
				content = LlamaCppMessageSerializer._create_multimodal_content(text_content, images)
				return {
					"role": "user",
					"content": content
				}
			else:
				# Text-only message
				return {
					"role": "user",
					"content": text_content or ""
				}

		elif isinstance(message, SystemMessage):
			text_content = LlamaCppMessageSerializer._extract_text_content(message.content)
			return {
				"role": "system",
				"content": text_content or ""
			}

		elif isinstance(message, AssistantMessage):
			# Handle content
			text_content = None
			if message.content is not None:
				text_content = LlamaCppMessageSerializer._extract_text_content(message.content)

			llama_message = {
				"role": "assistant",
				"content": text_content or ""
			}

			# Handle tool calls - llama.cpp server format may differ from OpenAI
			# For now, we'll convert to a simpler format or skip tool calls
			if message.tool_calls:
				# Convert tool calls to text description for now
				tool_descriptions = []
				for tool_call in message.tool_calls:
					try:
						args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
						tool_descriptions.append(f"Tool: {tool_call.function.name}, Args: {args}")
					except json.JSONDecodeError:
						tool_descriptions.append(f"Tool: {tool_call.function.name}, Args: {tool_call.function.arguments}")
				
				if tool_descriptions:
					tool_text = "\n".join(tool_descriptions)
					llama_message["content"] = f"{text_content or ''}\n\nTool Calls:\n{tool_text}".strip()

			return llama_message

		else:
			raise ValueError(f'Unknown message type: {type(message)}')

	@staticmethod
	def serialize_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
		"""Serialize a list of browser_use messages to llama.cpp server format."""
		return [LlamaCppMessageSerializer.serialize(m) for m in messages]