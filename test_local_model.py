#!/usr/bin/env python3
"""
Quick sanity test for local Ollama model (ChatOllama), without launching the browser.

It validates that:
- We can reach Ollama at OLLAMA_HOST
- The model responds and can satisfy a tiny structured-output schema

Usage:
  python test_local_model.py [model_override]

Defaults to OLLAMA_MODEL from env, or 'qwen2.5:14b-instruct-q2_k' if not provided.
"""

import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel

from browser_use import ChatOllama


class Ping(BaseModel):
    ok: bool
    note: str


async def main():
    load_dotenv()
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # Prefer CLI override -> env -> default q2_k for quick local test
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q2_k")

    llm = ChatOllama(model=model, host=host, timeout=60)

    # Keep the instruction minimal to exercise schema formatting
    system = (
        "You are a helpful assistant. Respond with strict JSON that matches the provided schema."
    )
    from browser_use.llm.messages import SystemMessage, UserMessage

    res = await llm.ainvoke(
        [
            SystemMessage(content=system),
            UserMessage(content="Return ok=true and a short note confirming local model responsiveness."),
        ],
        output_format=Ping,
    )

    print("Model:", model)
    print("Host:", host)
    print("Completion:", res.completion)


if __name__ == "__main__":
    asyncio.run(main())

