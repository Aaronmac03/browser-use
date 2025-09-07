---
description: Repository Information Overview
alwaysApply: true
---

# Browser-Use Information

## Summary
Browser-Use is an AI agent that autonomously interacts with the web. It takes user-defined tasks, navigates web pages using Chrome/Chromium via CDP (Chrome DevTools Protocol), processes HTML, and repeatedly queries language models to decide the next action until the task is completed. The project emphasizes privacy, cost-effectiveness, and the ability to handle complex multi-step tasks through an event-driven architecture.

## Current Version
**Version**: 0.7.3 (as of project files)
**Repository**: https://github.com/browser-use/browser-use
**Documentation**: https://docs.browser-use.com
**Cloud Service**: https://cloud.browser-use.com

## Architecture Overview
The library follows an event-driven architecture with several key components:
- **Agent**: Main orchestrator that manages browser sessions and executes LLM-driven action loops
- **BrowserSession**: Manages browser lifecycle, CDP connections, and coordinates watchdog services through an event bus
- **Tools Registry**: Action registry that maps LLM decisions to browser operations
- **DomService**: Extracts and processes DOM content, handles element highlighting
- **Event Bus (bubus)**: Coordinates watchdog services for downloads, popups, security, DOM processing

## Structure
- **browser_use/**: Core package with modular architecture
  - **agent/**: Agent service, prompts, and message management
  - **browser/**: Browser session management, profiles, and watchdogs
  - **llm/**: Multi-provider LLM integration (OpenAI, Anthropic, Google, Groq, Ollama, etc.)
  - **tools/**: Action registry and tool implementations
  - **dom/**: DOM processing and serialization
  - **mcp/**: Model Context Protocol client/server support
  - **sync/**: Synchronization and authentication services
  - **telemetry/**: Usage analytics and observability
- **examples/**: Sample code for various use cases and features
- **tests/**: Unit and integration tests (tests/ci/ for CI, tests/agent_tasks/ for E2E)
- **docs/**: Documentation files
- **runtime/**: Runtime data and user profiles

## Language & Runtime
**Language**: Python
**Version**: Python 3.11+ (supports up to Python 3.12)
**Build System**: Hatchling
**Package Manager**: uv (strongly preferred over pip)
**Code Style**: Tabs for indentation, modern Python typing (str | None, list[str])

## Dependencies
**Core Dependencies**:
- cdp-use (>=1.4.0): Chrome DevTools Protocol client with typed interfaces
- pydantic (>=2.11.5): Data validation and settings management
- bubus (>=1.5.6): Event bus system for watchdog coordination
- aiohttp (==3.12.15): Async HTTP client
- httpx (>=0.28.1): Modern HTTP client

**LLM Providers**:
- openai (>=1.99.2,<2.0.0): OpenAI GPT models
- anthropic (>=0.58.2,<1.0.0): Claude models
- google-genai (>=1.29.0,<2.0.0): Gemini models
- groq (>=0.30.0): Groq inference
- ollama (>=0.5.1): Local LLM integration

**Additional Features**:
- mcp (>=1.10.1): Model Context Protocol support
- pillow (>=11.2.1): Image processing
- pypdf (>=5.7.0): PDF handling
- html2text (>=2025.4.15): HTML to text conversion
- screeninfo (>=0.8.1): Display detection (Linux/Windows)
- pyobjc (>=11.0): macOS display detection

**Development Dependencies**:
- ruff (>=0.11.2): Linting and formatting
- pytest (>=8.3.5): Testing framework with asyncio support
- pytest-httpserver (>=1.0.8): HTTP server for testing
- pyright (>=1.1.403): Type checking
- pre-commit (>=4.2.0): Git hooks for code quality

## Build & Installation
```bash
# Recommended installation with uv
uv venv --python 3.11
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync

# Alternative with pip
pip install browser-use

# Install Chromium if needed
uvx playwright install chromium --with-deps --no-shell
```

## CLI Usage
Browser-Use includes a CLI interface:
```bash
# Run as MCP server
uvx browser-use[cli] --mcp

# Or use installed commands
browseruse --help
browser-use --help
```

## Testing
**Framework**: pytest with asyncio support and timeout handling
**Test Structure**:
- **tests/ci/**: Unit and integration tests (run by CI)
- **tests/agent_tasks/**: End-to-end agent task tests
- **tests/scripts/**: Debug and utility scripts
**Naming Convention**: test_*.py, *_test.py
**Configuration**: pytest.ini with asyncio_mode="auto", 300s timeout
**Run Commands**:
```bash
# Run CI tests
uv run pytest -vxs tests/ci/

# Run specific test
uv run pytest -vxs tests/ci/test_runner_e2e.py

# Run all tests
uv run pytest -vxs tests/

# Type checking
uv run pyright

# Linting and formatting
uv run ruff check --fix
uv run ruff format
```

## Basic Usage
```python
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI

# Basic agent setup
llm = ChatOpenAI(model="gpt-4o")
agent = Agent(
    task="Find the latest news about AI",
    llm=llm
)

# Run the agent
result = await agent.run()
```

## Local LLM Configuration
Browser-Use supports local LLMs through Ollama integration, ideal for privacy and cost-effectiveness:

```python
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI

# Local LLM configuration via Ollama
local_llm = ChatOpenAI(
    model="qwen2.5:7b-instruct-q4_k_m",  # Or other models available in Ollama
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Placeholder for Ollama
)

agent = Agent(
    task="Your task description",
    llm=local_llm
)
result = await agent.run()
```

## Browser Profile Configuration
To use your existing Chrome profile with Browser-Use:

```python
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI
from browser_use.browser import BrowserSession

# Configure browser with existing profile
browser = BrowserSession(
    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
    # executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
    user_data_dir="~/Library/Application Support/Google/Chrome",  # macOS
    # user_data_dir="%LOCALAPPDATA%\\Google\\Chrome\\User Data",  # Windows
    profile_directory="Default",  # Or your specific profile name
    headless=False
)

agent = Agent(
    task="Your task description",
    llm=ChatOpenAI(model="gpt-4o"),
    browser=browser
)
result = await agent.run()
```

## Multi-Provider LLM Support
Browser-Use supports multiple LLM providers with consistent interfaces:

```python
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI
from browser_use.llm.anthropic import ChatAnthropic
from browser_use.llm.google import ChatGoogle
from browser_use.llm.groq import ChatGroq
from browser_use.llm.ollama import ChatOllama

# OpenAI GPT models
openai_llm = ChatOpenAI(model="gpt-4o")

# Anthropic Claude models
claude_llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# Google Gemini models
gemini_llm = ChatGoogle(model="gemini-2.0-flash-exp")

# Groq inference
groq_llm = ChatGroq(model="llama-3.1-70b-versatile")

# Local Ollama models
ollama_llm = ChatOllama(model="qwen2.5:7b-instruct-q4_k_m")
```

## Tools and Actions
Browser-Use includes a comprehensive set of browser actions:

```python
from browser_use.tools import ToolRegistry

# Available actions include:
# - click_element: Click on web elements
# - type_text: Input text into fields
# - scroll: Scroll pages or elements
# - navigate_to_url: Navigate to URLs
# - take_screenshot: Capture screenshots
# - extract_text: Extract text content
# - get_dropdown_options: Get dropdown menu options
# - upload_file: Upload files to forms
# - download_file: Handle file downloads

# Custom tools can be registered
tools = ToolRegistry()

@tools.action(description="Custom web search action")
def web_search(query: str, num_results: int = 6) -> str:
    # Custom implementation
    return f"Search results for: {query}"
```

## MCP (Model Context Protocol) Integration
Browser-Use supports both MCP server and client modes:

```python
# Run as MCP server for Claude Desktop integration
# uvx browser-use[cli] --mcp

# Connect to external MCP servers as client
from browser_use.mcp.client import MCPClient

mcp_client = MCPClient()
# Connect to filesystem, GitHub, or other MCP servers
```

## Event-Driven Architecture
The library uses an event bus system for coordinating browser operations:

```python
# Watchdog services handle different aspects:
# - DownloadsWatchdog: File downloads and PDF handling
# - PopupsWatchdog: JavaScript dialogs and alerts
# - SecurityWatchdog: Domain restrictions and security
# - DOMWatchdog: DOM snapshots and element highlighting
# - AboutBlankWatchdog: Empty page redirects
```

## Development Guidelines
- Use async/await patterns throughout
- Use tabs for indentation (not spaces)
- Use modern Python typing: `str | None`, `list[str]`, `dict[str, Any]`
- Pydantic v2 models for data validation
- CDP-Use for typed Chrome DevTools Protocol access
- Event-driven architecture with bubus event bus
- Comprehensive testing with pytest and real browser instances