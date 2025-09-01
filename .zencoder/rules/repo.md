---
description: Repository Information Overview
alwaysApply: true
---

# Browser-Use Information

## Summary
Browser-Use is an AI agent that autonomously interacts with the web. It takes user-defined tasks, navigates web pages using Chrome/Chromium via CDP, processes HTML, and repeatedly queries language models to decide the next action until the task is completed. The project emphasizes privacy, cost-effectiveness, and the ability to handle complex multi-step tasks.

## Structure
- **browser_use/**: Core package with agent, browser, LLM, and tools implementations
- **examples/**: Sample code for various use cases and features
- **tests/**: Unit and integration tests
- **docs/**: Documentation files
- **runtime/**: Runtime data and user profiles

## Language & Runtime
**Language**: Python
**Version**: Python 3.11+
**Build System**: Hatchling
**Package Manager**: uv (preferred over pip)

## Dependencies
**Main Dependencies**:
- cdp-use: Chrome DevTools Protocol client
- pydantic: Data validation and settings management
- openai, anthropic, google-genai: Cloud LLM providers
- ollama: Local LLM integration
- httpx, aiohttp: Async HTTP clients
- mcp: Model Context Protocol support

**Development Dependencies**:
- ruff: Linting and formatting
- pytest, pytest-asyncio: Testing framework
- pre-commit: Git hooks for code quality

## Build & Installation
```bash
# Recommended installation with uv
uv venv --python 3.11
source .venv/bin/activate
uv sync

# Alternative with pip
pip install browser-use
```

## Testing
**Framework**: pytest with asyncio support
**Test Location**: tests/ci/ for unit/integration tests, tests/agent_tasks/ for end-to-end tests
**Naming Convention**: test_*.py, *_test.py
**Run Command**:
```bash
pytest tests/ci/
pytest tests/ci/test_runner_e2e.py  # For specific tests
```

## Local LLM Configuration
Browser-Use supports local LLMs through Ollama integration, ideal for privacy and cost-effectiveness:

```python
from browser_use import Agent, ChatOpenAI

# Local LLM configuration
local_llm = ChatOpenAI(
    model="qwen2.5:7b-instruct-q4_k_m",  # Or other models available in Ollama
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Placeholder for Ollama
)

agent = Agent(
    task="Your task description",
    llm=local_llm
)
await agent.run()
```

## Chrome Profile Integration
To use your existing Chrome profile with Browser-Use:

```python
from browser_use import Agent, ChatOpenAI, Browser

browser = Browser(
    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    user_data_dir="~/Library/Application Support/Google/Chrome",
    profile_directory="Default",  # Or your specific profile name
    headless=False
)

agent = Agent(
    task="Your task description",
    llm=ChatOpenAI(model="your-model"),
    browser=browser
)
await agent.run()
```

## Hybrid Model Approach
The runner.py script demonstrates a hybrid approach using local LLMs for most tasks and cloud models for planning:

```python
# Local LLM for agent actions
local_llm = make_local_llm()  # Uses Ollama

# Cloud LLM for planning and critical thinking
cloud_llm = make_o3_llm()  # Uses OpenAI

# Execute tasks with local LLM, fallback to cloud when needed
agent = Agent(
    task=title,
    llm=local_llm,
    tools=tools,
    browser=browser
)
```

## Web Search Integration
Serper.dev integration for web search capabilities:

```python
@tools.action(description="Google search via Serper.dev")
def web_search(query: str, num_results: int = 6) -> str:
    # Implementation using Serper API
    # Requires SERPER_API_KEY in environment
```