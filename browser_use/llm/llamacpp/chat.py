"""llama.cpp chat implementation for browser-use."""

import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

from .serializer import serialize_messages, deserialize_response

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatLlamaCpp(BaseChatModel):
    """llama.cpp chat implementation."""
    
    model: str
    base_url: str = "http://localhost:8080"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: float = 120.0
    
    @property
    def provider(self) -> str:
        return 'llamacpp'
    
    @property
    def name(self) -> str:
        return self.model
    
    def get_client(self) -> httpx.AsyncClient:
        """Get async HTTP client."""
        return httpx.AsyncClient(timeout=self.timeout)
    
    @overload
    async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...
    
    @overload
    async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...
    
    async def ainvoke(
        self, 
        messages: list[BaseMessage], 
        output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """Generate response using llama.cpp server."""
        try:
            # Serialize messages
            serialized_messages = serialize_messages(messages)
            
            # Prepare request payload
            payload = {
                "messages": serialized_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }
            
            # Add JSON format instruction if structured output is requested
            if output_format is not None:
                schema = output_format.model_json_schema()
                # Instead of using response_format (which may not be supported),
                # add JSON instruction to the last message
                if serialized_messages:
                    last_message = serialized_messages[-1]
                    if last_message.get("role") == "user":
                        json_instruction = f"\n\nPlease respond with valid JSON that matches this schema:\n{schema}\n\nRespond only with the JSON, no additional text."
                        last_message["content"] += json_instruction
                    else:
                        # Add a new user message with JSON instruction
                        serialized_messages.append({
                            "role": "user",
                            "content": f"Please respond with valid JSON that matches this schema:\n{schema}\n\nRespond only with the JSON, no additional text."
                        })
                
                # Try to use response_format if supported, but don't fail if not
                try:
                    payload["response_format"] = {"type": "json_object"}
                except:
                    pass  # Ignore if not supported
            
            # Make request to llama.cpp server
            async with self.get_client() as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise Exception(f"llama.cpp request failed: {response.status_code} - {response.text}")
                
                response_data = response.json()
                content = deserialize_response(response_data)
                
                # Handle structured output
                if output_format is not None:
                    try:
                        # First try to parse the content directly as JSON
                        completion = output_format.model_validate_json(content)
                    except Exception as e:
                        logger.warning(f"Failed to parse structured output directly: {e}")
                        # Fallback: try to extract JSON from content using multiple patterns
                        import re
                        import json
                        
                        # Try different JSON extraction patterns
                        patterns = [
                            r'\{.*\}',  # Basic JSON object
                            r'```json\s*(\{.*?\})\s*```',  # JSON in code blocks
                            r'```\s*(\{.*?\})\s*```',  # JSON in generic code blocks
                        ]
                        
                        json_text = None
                        for pattern in patterns:
                            match = re.search(pattern, content, re.DOTALL)
                            if match:
                                json_text = match.group(1) if match.groups() else match.group(0)
                                break
                        
                        if json_text:
                            try:
                                # Validate it's proper JSON first
                                json.loads(json_text)
                                completion = output_format.model_validate_json(json_text)
                            except Exception as parse_error:
                                logger.error(f"JSON extraction failed: {parse_error}")
                                raise Exception(f"Could not parse structured output. Content: {content[:200]}...")
                        else:
                            raise Exception(f"No JSON found in response. Content: {content[:200]}...")
                else:
                    completion = content
                
                return ChatInvokeCompletion(completion=completion, usage=None)
                
        except Exception as e:
            logger.error(f"Error generating response with llama.cpp: {e}")
            raise ModelProviderError(message=str(e), model=self.name) from e