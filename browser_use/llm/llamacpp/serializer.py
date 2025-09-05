"""Message serialization for llama.cpp integration."""

from typing import Any, Dict, List

from browser_use.llm.messages import (
    BaseMessage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
)


def _coerce_content_to_text(content: Any) -> str:
    """Best-effort conversion of message content (which may be text parts) to a plain string.

    - If content is a list of parts (e.g., ContentPartTextParam), join their text fields.
    - If content is a dict with a 'text' key, use it; otherwise JSON-dump it.
    - Otherwise, cast to string.
    """
    if content is None:
        return ""

    # Content as list of structured parts
    if isinstance(content, list):
        pieces: List[str] = []
        for part in content:
            # Structured part with attribute-style access
            if hasattr(part, "text") and isinstance(getattr(part, "text"), str):
                pieces.append(getattr(part, "text"))
            # Dict-style part
            elif isinstance(part, dict):
                txt = part.get("text")
                if isinstance(txt, str):
                    pieces.append(txt)
                else:
                    # Fallback stringification for non-text parts (e.g., images)
                    pieces.append(str(part))
            else:
                pieces.append(str(part))
        return "".join(pieces)

    # Single dict
    if isinstance(content, dict):
        txt = content.get("text")
        if isinstance(txt, str):
            return txt
        try:
            import json as _json

            return _json.dumps(content)
        except Exception:
            return str(content)

    # Plain string or other primitives
    return str(content)


def serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert browser-use messages to llama.cpp format with robust content handling."""
    serialized: List[Dict[str, Any]] = []

    for message in messages:
        if isinstance(message, SystemMessage):
            serialized.append({
                "role": "system",
                "content": _coerce_content_to_text(getattr(message, "content", None)),
            })
        elif isinstance(message, UserMessage):
            serialized.append({
                "role": "user",
                "content": _coerce_content_to_text(getattr(message, "content", None)),
            })
        elif isinstance(message, AssistantMessage):
            serialized.append({
                "role": "assistant",
                "content": _coerce_content_to_text(getattr(message, "content", None)),
            })

    return serialized


def deserialize_response(response: Dict[str, Any]) -> str:
    """Extract content from llama.cpp response."""
    if "choices" in response and len(response["choices"]) > 0:
        choice = response["choices"][0]
        if "message" in choice:
            return choice["message"].get("content", "")
        elif "text" in choice:
            return choice["text"]
    
    # Fallback for different response formats
    if "content" in response:
        return response["content"]
    
    return str(response)
