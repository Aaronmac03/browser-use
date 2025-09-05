"""llama.cpp chat implementation for browser-use."""

import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar, overload, List, Dict

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

            # If structured output requested, append JSON instruction before sizing
            if output_format is not None:
                schema = output_format.model_json_schema()
                if serialized_messages:
                    last_message = serialized_messages[-1]
                    if last_message.get("role") == "user":
                        json_instruction = (
                            "\n\nPlease respond with valid JSON that matches this schema:\n"
                            f"{schema}\n\nRespond only with the JSON, no additional text."
                        )
                        last_message["content"] = last_message.get("content", "") + json_instruction
                    else:
                        serialized_messages.append({
                            "role": "user",
                            "content": (
                                "Please respond with valid JSON that matches this schema:\n"
                                f"{schema}\n\nRespond only with the JSON, no additional text."
                            ),
                        })

            # Attempt request with shrink-on-retry to avoid 502s
            ATTEMPTS = 2
            LIMITS = [8000, 4000]

            for attempt in range(ATTEMPTS):
                limit = LIMITS[min(attempt, len(LIMITS) - 1)]
                msgs_to_send = _shrink_messages_to_limit(serialized_messages, limit)

                total_chars = sum(len(m.get("content", "")) for m in msgs_to_send)
                logger.debug(f"llamacpp request size attempt {attempt+1}/{ATTEMPTS}: {total_chars} chars, messages={len(msgs_to_send)}")
                if total_chars > 8000 and attempt == 0:
                    logger.warning(f"Large request detected: {total_chars} chars; will shrink further on retry if needed")

                # Prepare request payload
                payload = {
                    "messages": msgs_to_send,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": False,
                }
                # Try to use response_format if supported (nice-to-have)
                if output_format is not None:
                    try:
                        payload["response_format"] = {"type": "json_object"}
                    except Exception:
                        pass

                # Make request to llama.cpp server
                async with self.get_client() as client:
                    response = await client.post(
                        f"{self.base_url.rstrip('/')}/v1/chat/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                if response.status_code == 200:
                    response_data = response.json()
                    content = deserialize_response(response_data)

                    # Handle structured output
                    if output_format is not None:
                        try:
                            completion = output_format.model_validate_json(content)
                        except Exception as e:
                            logger.warning(f"Failed to parse structured output directly: {e}")
                            # Fallback: try to extract JSON from content using multiple patterns
                            import re as _re
                            import json as _json

                            patterns = [
                                r"\{.*\}",
                                r"```json\s*(\{.*?\})\s*```",
                                r"```\s*(\{.*?\})\s*```",
                            ]

                            json_text = None
                            for pattern in patterns:
                                match = _re.search(pattern, content, _re.DOTALL)
                                if match:
                                    json_text = match.group(1) if match.groups() else match.group(0)
                                    break

                            if json_text:
                                try:
                                    _json.loads(json_text)
                                    completion = output_format.model_validate_json(json_text)
                                except Exception as parse_error:
                                    logger.error(f"JSON extraction failed: {parse_error}")
                                    raise Exception(f"Could not parse structured output. Content: {content[:200]}...")
                            else:
                                raise Exception(f"No JSON found in response. Content: {content[:200]}...")
                    else:
                        completion = content

                    return ChatInvokeCompletion(completion=completion, usage=None)

                # Non-200: decide whether to retry smaller
                status = response.status_code
                body_preview = response.text[:200]
                logger.warning(f"llamacpp non-200 status={status}, body={body_preview}")
                retryable = status in (502, 413, 408, 429)
                if attempt < ATTEMPTS - 1 and retryable:
                    logger.info("Retrying with smaller payload due to server response")
                    continue
                raise Exception(f"llama.cpp request failed: {status} - {response.text}")

        except Exception as e:
            logger.error(f"Error generating response with llama.cpp: {e}")
            raise ModelProviderError(message=str(e), model=self.name) from e


def _truncate(text: str, limit: int) -> str:
    """Truncate a string to at most limit characters with ellipsis when needed."""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: max(0, limit - 1)] + "\u2026"


def _shrink_messages_to_limit(messages: List[Dict[str, Any]], max_total_chars: int) -> List[Dict[str, Any]]:
    """Shrink an OpenAI-style messages list to fit within max_total_chars.

    Strategy:
    - Preserve the last system message and the last user message.
    - Drop oldest non-essential messages first.
    - If still too large, truncate contents starting from the largest.
    - Apply conservative per-message caps to avoid a single large DOM blob.
    """
    # Fast path
    total = sum(len(m.get("content", "")) for m in messages)
    if total <= max_total_chars:
        return messages

    msgs = [dict(m) for m in messages]

    # Identify anchor indices to preserve
    last_sys = max((i for i, m in enumerate(msgs) if m.get("role") == "system"), default=None)
    last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=None)
    last_asst = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"), default=None)

    def is_anchor(idx: int) -> bool:
        return idx in {last_sys, last_user, last_asst}

    # 1) Drop oldest non-anchors until under limit or only anchors remain
    i = 0
    while i < len(msgs) and sum(len(m.get("content", "")) for m in msgs) > max_total_chars:
        if not is_anchor(i):
            msgs.pop(i)
            # do not increment i to re-check same index after pop
            continue
        i += 1

    # 2) If still too large, apply truncation caps per message
    if sum(len(m.get("content", "")) for m in msgs) > max_total_chars:
        # Initial per-message caps (system small, user larger)
        caps = {
            "system": 1500,
            "user": 4000,
            "assistant": 1500,
        }
        # Apply caps
        for m in msgs:
            role = m.get("role", "user")
            cap = caps.get(role, 1500)
            m["content"] = _truncate(m.get("content", ""), cap)

        # 3) If still over, iteratively trim the largest content
        while sum(len(m.get("content", "")) for m in msgs) > max_total_chars and msgs:
            # Find the message with the largest content (prefer trimming user/assistant before system)
            idx = max(range(len(msgs)), key=lambda j: (len(msgs[j].get("content", "")), msgs[j].get("role") == "system"))
            txt = msgs[idx].get("content", "")
            if len(txt) <= 200:
                # Nothing meaningful left to trim
                break
            new_len = max(200, len(txt) // 2)
            msgs[idx]["content"] = _truncate(txt, new_len)

    return msgs
