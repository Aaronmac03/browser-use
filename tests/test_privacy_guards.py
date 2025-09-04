#!/usr/bin/env python3
"""
Privacy guard tests to ensure no page content is sent to cloud LLMs.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import sys
import os

# Add the browser-use directory to the path so we can import runner
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import plan_with_o3_then_gemini, critic_with_o3_then_gemini, redact_page_content


class TestPrivacyGuards:
    """Test suite to ensure no page content leaks to cloud LLMs."""
    
    def test_redact_page_content_removes_html_tags(self):
        """Test that HTML tags are stripped from content."""
        html_content = "<div class='content'><p>Some text</p><script>alert('test')</script></div>"
        redacted = redact_page_content(html_content)
        
        assert "<div" not in redacted
        assert "<p>" not in redacted
        assert "<script>" not in redacted
        assert "Some text" in redacted
        assert "alert('test')" in redacted
    
    def test_redact_page_content_removes_base64(self):
        """Test that base64-like strings are redacted."""
        content_with_base64 = "Normal text iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg== more text"
        redacted = redact_page_content(content_with_base64)
        
        assert "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" not in redacted
        assert "[REDACTED_BASE64]" in redacted
        assert "Normal text" in redacted
        assert "more text" in redacted
    
    def test_redact_page_content_truncates_long_tokens(self):
        """Test that very long tokens are truncated."""
        long_token = "a" * 250  # 250 character token
        content = f"Normal text {long_token} more text"
        redacted = redact_page_content(content)
        
        assert long_token not in redacted
        assert "[REDACTED_LONG_TOKEN]" in redacted
        assert "Normal text" in redacted
        assert "more text" in redacted
    
    @pytest.mark.asyncio
    async def test_planner_no_page_content_sent_to_cloud(self):
        """Test that planner functions don't send DOM/page content to cloud."""
        captured_prompts = []
        
        def capture_prompt(messages, **kwargs):
            # Capture the content of messages sent to cloud LLM
            for msg in messages:
                if hasattr(msg, 'content'):
                    captured_prompts.append(msg.content)
            # Return a mock response
            mock_response = MagicMock()
            mock_response.completion = '{"subtasks": [{"title": "test", "instructions": "test", "success": "test"}]}'
            return mock_response
        
        # Mock both OpenAI and Anthropic clients
        with patch('browser_use.ChatOpenAI.ainvoke', side_effect=capture_prompt) as mock_openai:
            # Test with a goal that doesn't contain page content
            goal = "Navigate to example.com and find the contact page"
            
            try:
                await plan_with_o3_then_gemini(goal)
            except Exception:
                pass  # We expect JSON parsing to fail with our mock, that's OK
            
            # Verify that captured prompts only contain the goal, not page content
            # The goal should be in the UserMessage, not the SystemMessage
            goal_found = False
            for prompt in captured_prompts:
                if goal in prompt:
                    goal_found = True
                assert "<div" not in prompt  # No HTML tags
                assert "<html>" not in prompt  # No HTML structure
                assert "document.getElementById" not in prompt  # No JS
                # Check for common DOM-like patterns that shouldn't be there
                assert not any(tag in prompt.lower() for tag in ["<body>", "<head>", "<script>", "<style>"])
            
            # Ensure the goal was found in at least one of the messages
            assert goal_found, f"Goal '{goal}' not found in any captured prompts: {captured_prompts}"
    
    @pytest.mark.asyncio
    async def test_critic_redacts_observation_content(self):
        """Test that critic function redacts page content from observations."""
        captured_prompts = []
        
        def capture_prompt(messages, **kwargs):
            for msg in messages:
                if hasattr(msg, 'content'):
                    captured_prompts.append(msg.content)
            mock_response = MagicMock()
            mock_response.completion = "Analysis of the issue"
            return mock_response
        
        # Create observation with HTML content that should be redacted
        observation_with_html = """
        Error occurred while processing page:
        <div class="error-container">
            <p>Page failed to load</p>
            <script>console.log('debug info')</script>
        </div>
        Additional context with base64: iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
        """
        
        subtask = "Navigate to contact page"
        
        with patch('browser_use.ChatOpenAI.ainvoke', side_effect=capture_prompt):
            try:
                await critic_with_o3_then_gemini(observation_with_html, subtask)
            except Exception:
                pass  # Mock response handling may fail, that's OK
            
            # Verify that HTML and base64 content was redacted
            for prompt in captured_prompts:
                if "OBSERVATION:" in prompt:
                    assert "<div" not in prompt
                    assert "<script>" not in prompt
                    assert "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" not in prompt
                    assert "[REDACTED_BASE64]" in prompt
                    assert "Error occurred while processing page:" in prompt  # Non-HTML content should remain
    
    @pytest.mark.asyncio
    async def test_critic_with_gemini_fallback_also_redacts(self):
        """Test that Gemini fallback also redacts content."""
        observation_with_sensitive_data = """
        <html><body><div id="sensitive">Secret API key: sk-1234567890abcdef</div></body></html>
        Very long token: """ + "x" * 250
        
        subtask = "Test task"
        
        # Mock gemini_text function to capture what's sent
        captured_gemini_prompts = []
        
        async def mock_gemini_text(prompt):
            captured_gemini_prompts.append(prompt)
            return "Gemini analysis"
        
        # Force OpenAI to fail so it falls back to Gemini
        with patch('browser_use.ChatOpenAI.ainvoke', side_effect=Exception("OpenAI failed")):
            with patch('runner.gemini_text', side_effect=mock_gemini_text):
                result = await critic_with_o3_then_gemini(observation_with_sensitive_data, subtask)
                
                assert result == "Gemini analysis"
                assert len(captured_gemini_prompts) == 1
                
                gemini_prompt = captured_gemini_prompts[0]
                # Verify redaction occurred
                assert "<html>" not in gemini_prompt
                assert "<body>" not in gemini_prompt
                assert "sk-1234567890abcdef" in gemini_prompt  # API key pattern should remain (it's not HTML/base64)
                assert "[REDACTED_LONG_TOKEN]" in gemini_prompt  # Long token should be redacted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])