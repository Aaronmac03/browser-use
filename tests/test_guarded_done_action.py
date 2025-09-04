#!/usr/bin/env python3
"""
Tests for guarded done action heuristics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the browser-use directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import build_tools_for_subtask
from browser_use.tools.views import DoneAction
from browser_use.browser.views import BrowserStateSummary
from browser_use.dom.views import SerializedDOMState
from browser_use.agent.views import ActionResult


class TestGuardedDoneAction:
    """Test suite for guarded done action validation logic."""
    
    def create_mock_browser_state(self, url="https://example.com", title="Example Page", dom_content="<div>Page content</div>"):
        """Helper to create mock browser state."""
        mock_state = MagicMock(spec=BrowserStateSummary)
        mock_state.url = url
        mock_state.title = title
        
        # Mock DOM state
        mock_dom = MagicMock(spec=SerializedDOMState)
        mock_dom.llm_representation.return_value = dom_content
        mock_state.dom_state = mock_dom
        
        return mock_state
    
    @pytest.mark.asyncio
    async def test_done_blocks_about_blank_pages(self):
        """Test that done action is blocked on about:blank pages."""
        tools = build_tools_for_subtask("Test task", "Navigate to example.com", "Page loads successfully")
        
        # Get the done action
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        assert done_func is not None
        
        # Mock browser session that returns about:blank
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(url="about:blank")
        )
        
        # Try to complete task
        params = DoneAction(success=True, text="Task completed")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be blocked
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "not on a meaningful page" in result.error
        assert result.is_done is not True
    
    @pytest.mark.asyncio
    async def test_done_blocks_chrome_pages(self):
        """Test that done action is blocked on chrome:// pages."""
        tools = build_tools_for_subtask("Test task", "Navigate to example.com", "Page loads successfully")
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(url="chrome://settings")
        )
        
        params = DoneAction(success=True, text="Task completed")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "not on a meaningful page" in result.error
    
    @pytest.mark.asyncio
    async def test_done_requires_web_search_for_search_tasks(self):
        """Test that search tasks require web_search to be used first."""
        tools = build_tools_for_subtask("Find information", "Search for Python tutorials", "Find relevant tutorials")
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(url="https://example.com", dom_content="<div>Python tutorial content</div>")
        )
        
        # Try to complete without using web_search
        params = DoneAction(success=True, text="Found tutorials")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be blocked because web_search wasn't used
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "Use web_search" in result.error
    
    @pytest.mark.asyncio
    async def test_done_allows_completion_after_web_search(self):
        """Test that search tasks are allowed after web_search is used."""
        tools = build_tools_for_subtask("Find information", "Search for Python tutorials", "Find relevant tutorials")
        
        # First use web_search to set the usage flag
        web_search_func = None
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "web_search":
                web_search_func = action_info.function
            elif action_name == "done":
                done_func = action_info.function
        
        assert web_search_func is not None
        assert done_func is not None
        
        # Mock successful web search
        with patch('httpx.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"organic": []}
            mock_post.return_value = mock_response
            
            with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
                # Use web_search first (it's async now)
                await web_search_func(query="Python tutorials")
        
        # Now try to complete
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(
                url="https://python.org/tutorials", 
                dom_content="<div>Python tutorials found</div>"
            )
        )
        
        params = DoneAction(success=True, text="Found Python tutorials")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be allowed now
        assert isinstance(result, ActionResult)
        assert result.is_done is True
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_done_checks_domain_matching(self):
        """Test that done action checks if we're on the referenced domain."""
        tools = build_tools_for_subtask(
            "Navigate to GitHub", 
            "Go to github.com pricing page", 
            "Successfully reach github.com pricing"
        )
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        # Try to complete while on wrong domain
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(url="https://example.com")
        )
        
        params = DoneAction(success=True, text="Task completed")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be blocked because we're not on github.com
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "Navigate to the referenced domain" in result.error
    
    @pytest.mark.asyncio
    async def test_done_allows_completion_on_correct_domain(self):
        """Test that done action allows completion when on the correct domain."""
        tools = build_tools_for_subtask(
            "Navigate to GitHub", 
            "Go to github.com pricing page", 
            "Successfully reach github.com pricing"
        )
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        # Complete while on correct domain
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(
                url="https://github.com/pricing",
                title="GitHub Pricing",
                dom_content="<div>GitHub pricing information</div>"
            )
        )
        
        params = DoneAction(success=True, text="Found GitHub pricing page")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be allowed
        assert isinstance(result, ActionResult)
        assert result.is_done is True
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_done_checks_success_criteria_keywords(self):
        """Test that done action checks for success criteria keywords on page."""
        tools = build_tools_for_subtask(
            "Contact info task", 
            "Navigate to company website", 
            "Locate contact information and phone number"
        )
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        # Try to complete on page without success criteria keywords
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(
                url="https://company.com",
                dom_content="<div>About us page with company history and mission</div>"
            )
        )
        
        params = DoneAction(success=True, text="Task completed")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be blocked because success keywords not found
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "On-page evidence for success criteria not found" in result.error
    
    @pytest.mark.asyncio
    async def test_done_allows_completion_with_success_keywords(self):
        """Test that done action allows completion when success keywords are present."""
        tools = build_tools_for_subtask(
            "Contact info task", 
            "Navigate to company website", 
            "Locate contact information and phone number"
        )
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        # Complete on page with success criteria keywords
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(
                url="https://company.com/contact",
                title="Contact Information",
                dom_content="<div>Contact information: phone number (555) 123-4567</div>"
            )
        )
        
        params = DoneAction(success=True, text="Found contact information with phone number")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be allowed
        assert isinstance(result, ActionResult)
        assert result.is_done is True
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_done_allows_failure_completion(self):
        """Test that done action allows completion when success=False."""
        tools = build_tools_for_subtask("Test task", "Do something", "Success criteria")
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            return_value=self.create_mock_browser_state(url="https://example.com")
        )
        
        # Complete with success=False
        params = DoneAction(success=False, text="Task failed due to technical issues")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be allowed even without meeting success criteria
        assert isinstance(result, ActionResult)
        assert result.is_done is True
        assert result.success is False
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_done_handles_browser_state_errors(self):
        """Test that done action handles browser state retrieval errors gracefully."""
        tools = build_tools_for_subtask("Test task", "Do something", "Success criteria")
        
        done_func = None
        for action_name, action_info in tools.registry.registry.actions.items():
            if action_name == "done":
                done_func = action_info.function
                break
        
        # Mock browser session that throws error
        mock_browser_session = MagicMock()
        mock_browser_session.get_browser_state_summary = AsyncMock(
            side_effect=Exception("Browser state error")
        )
        
        params = DoneAction(success=True, text="Task completed")
        result = await done_func(params=params, browser_session=mock_browser_session)
        
        # Should be blocked with error message
        assert isinstance(result, ActionResult)
        assert result.error is not None
        assert "Cannot complete yet: failed to inspect page state" in result.error
        assert result.is_done is not True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])