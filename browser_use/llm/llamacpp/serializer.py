"""Message serialization for llama.cpp integration."""

from typing import Any, Dict, List

from browser_use.llm.messages import BaseMessage, SystemMessage, UserMessage, AssistantMessage


def serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert browser-use messages to llama.cpp format."""
    serialized = []
    
    for message in messages:
        if isinstance(message, SystemMessage):
            serialized.append({
                "role": "system",
                "content": message.content
            })
        elif isinstance(message, UserMessage):
            serialized.append({
                "role": "user", 
                "content": message.content
            })
        elif isinstance(message, AssistantMessage):
            serialized.append({
                "role": "assistant",
                "content": message.content
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