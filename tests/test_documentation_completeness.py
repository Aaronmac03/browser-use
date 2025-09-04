#!/usr/bin/env python3

"""
Test suite to validate documentation completeness and accuracy.
"""

import os
import sys
from pathlib import Path
import pytest

# Add the parent directory to sys.path so we can import browser_use modules
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDocumentationCompleteness:
	"""Test documentation exists and covers critical areas."""
	
	def test_usage_documentation_exists(self):
		"""Test that usage documentation file exists."""
		docs_path = Path(__file__).parent.parent / "docs" / "USAGE.md"
		assert docs_path.exists(), "USAGE.md documentation should exist"
	
	def test_usage_documentation_covers_hybrid_setup(self):
		"""Test that usage docs cover hybrid LLM setup."""
		docs_path = Path(__file__).parent.parent / "docs" / "USAGE.md"
		if docs_path.exists():
			content = docs_path.read_text(encoding='utf-8')
			assert "hybrid" in content.lower(), "Usage docs should mention hybrid setup"
			assert "local llm" in content.lower() or "local model" in content.lower(), "Usage docs should cover local LLM setup"
			assert "cloud model" in content.lower() or "claude" in content.lower() or "gpt" in content.lower(), "Usage docs should cover cloud models"
	
	def test_usage_documentation_covers_hardware_optimization(self):
		"""Test that usage docs cover hardware optimization."""
		docs_path = Path(__file__).parent.parent / "docs" / "USAGE.md"
		if docs_path.exists():
			content = docs_path.read_text(encoding='utf-8')
			assert "gtx 1660" in content.lower() or "gpu" in content.lower(), "Usage docs should mention GPU optimization"
			assert "performance" in content.lower(), "Usage docs should cover performance"
	
	def test_usage_documentation_covers_chrome_profiles(self):
		"""Test that usage docs cover Chrome profile setup."""
		docs_path = Path(__file__).parent.parent / "docs" / "USAGE.md"
		if docs_path.exists():
			content = docs_path.read_text(encoding='utf-8')
			assert "chrome profile" in content.lower() or "browser profile" in content.lower(), "Usage docs should cover Chrome profiles"
			assert "account" in content.lower(), "Usage docs should mention account usage"
	
	def test_best_practices_documentation_exists(self):
		"""Test that best practices documentation exists."""
		docs_path = Path(__file__).parent.parent / "docs" / "BEST_PRACTICES.md"
		assert docs_path.exists(), "BEST_PRACTICES.md documentation should exist"
	
	def test_best_practices_covers_privacy(self):
		"""Test that best practices cover privacy considerations."""
		docs_path = Path(__file__).parent.parent / "docs" / "BEST_PRACTICES.md"
		if docs_path.exists():
			content = docs_path.read_text(encoding='utf-8')
			assert "privacy" in content.lower(), "Best practices should cover privacy"
			assert "local" in content.lower(), "Best practices should emphasize local processing"
	
	def test_best_practices_covers_cost_optimization(self):
		"""Test that best practices cover cost optimization."""
		docs_path = Path(__file__).parent.parent / "docs" / "BEST_PRACTICES.md"
		if docs_path.exists():
			content = docs_path.read_text(encoding='utf-8')
			assert "cost" in content.lower(), "Best practices should cover cost optimization"
			assert "local llm" in content.lower() or "local model" in content.lower(), "Best practices should recommend local LLMs"
	
	def test_example_workflows_exist(self):
		"""Test that example workflows exist."""
		examples_dir = Path(__file__).parent.parent / "examples"
		assert examples_dir.exists(), "Examples directory should exist"
		
		# Check for at least 3 example workflows (including subdirectories)
		example_files = list(examples_dir.glob("**/*.py"))
		# Filter out __init__.py files
		example_files = [f for f in example_files if not f.name.startswith('__')]
		assert len(example_files) >= 3, f"Should have at least 3 example workflows, found {len(example_files)}"
	
	def test_configuration_templates_exist(self):
		"""Test that configuration templates exist."""
		# Check for .env.example
		env_example = Path(__file__).parent.parent / ".env.example"
		assert env_example.exists(), ".env.example should exist as configuration template"
		
		# Check it contains key configuration options
		if env_example.exists():
			content = env_example.read_text(encoding='utf-8')
			assert "LLAMACPP_HOST" in content or "LOCAL_LLM_URL" in content, ".env.example should include local LLM configuration"
			assert "ANTHROPIC_API_KEY" in content or "OPENAI_API_KEY" in content, ".env.example should include cloud API configuration"


if __name__ == "__main__":
	pytest.main([__file__, "-v"])