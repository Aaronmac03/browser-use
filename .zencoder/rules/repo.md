---
description: Repository Information Overview
alwaysApply: true
---

# Browser-Use Information

## Summary
Browser-Use is a Python library that enables AI agents to control web browsers. It provides a framework for automating browser interactions, allowing AI to perform tasks like web searches, form filling, data extraction, and multi-step workflows. The library supports various LLM providers and includes features for custom functions, structured output, and secure handling of sensitive data.

## Structure
- **browser_use/**: Core package containing the main implementation
  - **agent/**: AI agent implementation for browser control
  - **browser/**: Browser automation and control components
  - **dom/**: DOM manipulation and page state representation
  - **llm/**: Integrations with various LLM providers
  - **mcp/**: Model Context Protocol implementation
- **examples/**: Sample code demonstrating various use cases
- **tests/**: Test suite for CI and functionality verification
- **docs/**: Documentation files for the project
- **docker/**: Docker configuration for containerized deployment

## Language & Runtime
**Language**: Python
**Version**: 3.12 (supports >=3.11,<4.0)
**Build System**: Hatchling
**Package Manager**: pip/uv

## Dependencies
**Main Dependencies**:
- playwright: Browser automation
- pydantic: Data validation and settings management
- httpx: HTTP client
- anthropic, openai, google-genai, groq: LLM provider clients
- aiohttp, anyio: Async I/O utilities
- mcp: Model Context Protocol support
- cdp-use: Chrome DevTools Protocol utilities

**Development Dependencies**:
- ruff: Linting and formatting
- pytest, pytest-asyncio: Testing framework
- pyright: Type checking
- pre-commit: Git hooks for code quality

## Build & Installation
```bash
pip install browser-use
uvx playwright install chromium --with-deps --no-shell
```

## Docker
**Dockerfile**: Dockerfile, Dockerfile.fast
**Image**: Python 3.12-slim based image with Chromium
**Configuration**: Multi-stage build with playwright and browser-use dependencies

## Testing
**Framework**: pytest with asyncio support
**Test Location**: tests/ directory with ci/ and agent_tasks/ subdirectories
**Naming Convention**: test_*.py
**Configuration**: pytest.ini_options in pyproject.toml
**Run Command**:
```bash
pytest tests/
```

## CLI
**Entry Point**: browser_use.cli:main
**Commands**: browseruse, browser-use
**Dependencies**: rich, click, textual (optional)

## MCP Integration
**Server**: Implements MCP server for Claude Desktop integration
**Client**: Can connect to external MCP servers for extended capabilities
**Configuration**: JSON-based configuration for server registration