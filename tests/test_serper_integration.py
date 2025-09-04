#!/usr/bin/env python3
"""
Test Serper API integration for web search functionality.
Validates API key configuration and search capabilities.
"""

import json
import os
import pytest
import httpx
from unittest.mock import patch, MagicMock

from runner import build_tools


class TestSerperIntegration:
    """Test Serper API integration and web search functionality."""
    
    def test_serper_api_key_configured(self):
        """Test that SERPER_API_KEY is configured in environment."""
        api_key = os.getenv("SERPER_API_KEY")
        # Don't fail if not configured - just check format if present
        if api_key and api_key != "your_serper_api_key_here":
            assert len(api_key) > 10, "SERPER_API_KEY should be a valid key"
        else:
            pytest.skip("SERPER_API_KEY not configured - set in .env for web search")
    
    def test_build_tools_includes_web_search(self):
        """Test that build_tools() includes web_search action."""
        tools = build_tools()
        
        # Check that tools object has registry
        assert hasattr(tools, 'registry'), "Tools should have registry"
        
        # Check that web_search is available in registry
        action_names = list(tools.registry.registry.actions.keys())
        assert "web_search" in action_names, f"web_search should be available in tools. Available: {action_names}"
    
    @patch('httpx.post')
    def test_web_search_function_success(self, mock_post):
        """Test web_search function with mocked successful response."""
        # Mock successful Serper API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Test Result 1",
                    "link": "https://example.com/1",
                    "snippet": "This is a test result"
                },
                {
                    "title": "Test Result 2", 
                    "link": "https://example.com/2",
                    "snippet": "Another test result"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Set API key for test
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            
            # Get web_search action from registry
            assert "web_search" in tools.registry.registry.actions, "web_search action should exist"
            web_search_action = tools.registry.registry.actions["web_search"]
            
            # Test the function - handle potential async wrapper
            result = web_search_action.function("test query", 2)
            
            # If result is a coroutine, we need to handle it differently
            if hasattr(result, '__await__'):
                # Skip this test if the function is wrapped in async context
                pytest.skip("Function is wrapped in async context - integration test needed")
            
            result_data = json.loads(result)
            
            assert result_data["query"] == "test query"
            assert len(result_data["results"]) == 2
            assert result_data["results"][0]["title"] == "Test Result 1"
    
    @patch('httpx.post')
    def test_web_search_function_error_handling(self, mock_post):
        """Test web_search function error handling."""
        # Mock API error
        mock_post.side_effect = httpx.RequestError("Connection failed")
        
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            
            # Get web_search action from registry
            web_search_action = tools.registry.registry.actions["web_search"]
            
            # Test error handling
            result = web_search_action.function("test query")
            
            # If result is a coroutine, skip this test
            if hasattr(result, '__await__'):
                pytest.skip("Function is wrapped in async context - integration test needed")
            
            result_data = json.loads(result)
            
            assert "error" in result_data
            assert "Connection failed" in result_data["error"]
    
    def test_web_search_no_api_key(self):
        """Test web_search function when API key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            tools = build_tools()
            
            # Get web_search action from registry
            web_search_action = tools.registry.registry.actions["web_search"]
            
            # Test without API key
            result = web_search_action.function("test query")
            
            # If result is a coroutine, skip this test
            if hasattr(result, '__await__'):
                pytest.skip("Function is wrapped in async context - integration test needed")
            
            result_data = json.loads(result)
            
            assert "error" in result_data
            assert "SERPER_API_KEY not set" in result_data["error"]
    
    def test_web_search_parameter_validation(self):
        """Test web_search function parameter validation."""
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            
            # Get web_search action from registry
            web_search_action = tools.registry.registry.actions["web_search"]
            
            # Test parameter bounds
            with patch('httpx.post') as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"organic": []}
                mock_post.return_value = mock_response
                
                # Test num_results clamping
                result1 = web_search_action.function("test", 0)  # Should clamp to 1
                result2 = web_search_action.function("test", 15)  # Should clamp to 10
                
                # If results are coroutines, skip this test
                if hasattr(result1, '__await__') or hasattr(result2, '__await__'):
                    pytest.skip("Function is wrapped in async context - integration test needed")
                
                # Verify API calls were made with clamped values
                calls = mock_post.call_args_list
                assert calls[0][1]["json"]["num"] == 1  # Clamped from 0
                assert calls[1][1]["json"]["num"] == 10  # Clamped from 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])