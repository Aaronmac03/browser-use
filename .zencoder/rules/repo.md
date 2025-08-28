---
description: Repository Information Overview
alwaysApply: true
---

# Browser-Use Information

## Summary
Browser-Use is an AI agent that autonomously interacts with the web. It takes user-defined tasks, navigates web pages using Chromium via CDP, processes HTML, and repeatedly queries language models (like GPT-4o) to decide the next action until the task is completed.

## Structure
- **browser_use/**: Core package with agent, browser, controller, and LLM integrations
- **examples/**: Sample code demonstrating various use cases and features
- **tests/**: Comprehensive test suite with CI tests and agent task evaluations
- **docs/**: Documentation including architecture, roadmap, and API reference
- **bin/**: Utility scripts and executables
- **static/**: Static assets like logos and images

## Language & Runtime
**Language**: Python
**Version**: Python 3.11+
**Build System**: Hatchling
**Package Manager**: uv (recommended over pip)

## Dependencies
**Main Dependencies**:
- cdp-use (≥1.4.0): Chrome DevTools Protocol integration
- pydantic (≥2.11.5): Data validation and settings management
- aiohttp (3.12.15): Async HTTP client/server
- openai (1.99.2): OpenAI API client
- anthropic (0.58.2): Anthropic API client
- google-genai (1.29.0): Google AI API client
- mcp (≥1.10.1): Model Context Protocol support

**Development Dependencies**:
- ruff (≥0.11.2): Python linter
- pytest (≥8.3.5): Testing framework
- pytest-asyncio (≥1.0.0): Async testing support
- pyright (≥1.1.403): Type checking

## Build & Installation
```bash
# Install with pip
pip install browser-use

# Recommended installation with uv
uv venv --python 3.11
source .venv/bin/activate
uv sync

# Install browser dependencies
uvx playwright install chromium --with-deps --no-shell
```

## Docker
**Dockerfile**: Dockerfile, Dockerfile.fast
**Image**: browseruse/browseruse
**Configuration**: Multi-arch build (amd64, arm64) with Python 3.12, Chromium, and all dependencies

## Testing
**Framework**: pytest with pytest-asyncio
**Test Location**: tests/ci/ for CI tests, tests/agent_tasks/ for agent evaluations
**Configuration**: pytest.ini_options in pyproject.toml
**Run Command**:
```bash
pytest tests/ci/
```

## MCP Integration
Browser-Use supports the Model Context Protocol (MCP), enabling integration with Claude Desktop and other MCP-compatible clients. It can function as both an MCP server and client.

## CLI Interface
**Command**: browser-use or browseruse
**Configuration**: Optional dependencies in [project.optional-dependencies] cli section
```bash
browser-use --version
browser-use --mcp  # Start as MCP server
```