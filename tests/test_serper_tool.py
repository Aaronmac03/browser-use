#!/usr/bin/env python3
"""
Tests for Serper web search tool behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add the browser-use directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import build_tools


class TestSerperTool:
    """Test suite for Serper web search tool."""
    
    def test_web_search_missing_api_key(self):
        """Test that missing SERPER_API_KEY returns friendly error."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear SERPER_API_KEY from environment
            tools = build_tools()
            
            # Get the web_search function
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            assert web_search_func is not None, "web_search function not found in tools"
            
            # Call web_search without API key
            result = web_search_func("test query")
            
            # Should return JSON error
            result_data = json.loads(result)
            assert "error" in result_data
            assert "SERPER_API_KEY not set" in result_data["error"]
    
    @patch('httpx.post')
    def test_web_search_successful_response(self, mock_post):
        """Test successful web search with proper schema."""
        # Mock successful Serper API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Example Result 1",
                    "link": "https://example1.com",
                    "snippet": "This is the first example result",
                    "extra_field": "should be ignored"
                },
                {
                    "title": "Example Result 2", 
                    "link": "https://example2.com",
                    "snippet": "This is the second example result"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Set API key and create tools
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            
            # Get the web_search function
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            # Call web_search
            result = web_search_func("test query", 2)
            
            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://google.serper.dev/search"
            assert call_args[1]["headers"]["X-API-KEY"] == "test_key"
            assert call_args[1]["json"]["q"] == "test query"
            assert call_args[1]["json"]["num"] == 2
            
            # Verify response format
            result_data = json.loads(result)
            assert "query" in result_data
            assert "results" in result_data
            assert result_data["query"] == "test query"
            assert len(result_data["results"]) == 2
            
            # Verify schema - only title, link, snippet should be present
            for result_item in result_data["results"]:
                assert set(result_item.keys()) == {"title", "link", "snippet"}
                assert "extra_field" not in result_item
    
    @patch('httpx.post')
    def test_web_search_num_results_clamping(self, mock_post):
        """Test that num_results is properly clamped to 1-10 range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"organic": []}
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            # Test clamping to minimum (1)
            web_search_func("test", 0)
            call_args = mock_post.call_args
            assert call_args[1]["json"]["num"] == 1
            
            # Test clamping to maximum (10)
            web_search_func("test", 15)
            call_args = mock_post.call_args
            assert call_args[1]["json"]["num"] == 10
            
            # Test normal value
            web_search_func("test", 5)
            call_args = mock_post.call_args
            assert call_args[1]["json"]["num"] == 5
    
    @patch('httpx.post')
    def test_web_search_result_truncation(self, mock_post):
        """Test that results are truncated to requested num_results."""
        # Mock response with more results than requested
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "organic": [
                {"title": f"Result {i}", "link": f"https://example{i}.com", "snippet": f"Snippet {i}"}
                for i in range(1, 8)  # 7 results
            ]
        }
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            # Request only 3 results
            result = web_search_func("test query", 3)
            result_data = json.loads(result)
            
            # Should only return 3 results despite API returning 7
            assert len(result_data["results"]) == 3
            assert result_data["results"][0]["title"] == "Result 1"
            assert result_data["results"][2]["title"] == "Result 3"
    
    @patch('httpx.post')
    def test_web_search_http_error_handling(self, mock_post):
        """Test that HTTP errors are handled gracefully."""
        # Mock HTTP error
        mock_post.side_effect = Exception("Network error")
        
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            result = web_search_func("test query")
            result_data = json.loads(result)
            
            assert "error" in result_data
            assert "Network error" in result_data["error"]
    
    @patch('httpx.post')
    def test_web_search_malformed_response_handling(self, mock_post):
        """Test handling of malformed API responses."""
        # Mock response with missing organic field
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"someOtherField": "value"}
        mock_post.return_value = mock_response
        
        with patch.dict(os.environ, {"SERPER_API_KEY": "test_key"}):
            tools = build_tools()
            web_search_func = None
            for action_name, action_info in tools._registry.items():
                if action_name == "web_search":
                    web_search_func = action_info.func
                    break
            
            result = web_search_func("test query")
            result_data = json.loads(result)
            
            # Should handle missing organic field gracefully
            assert "query" in result_data
            assert "results" in result_data
            assert result_data["results"] == []  # Empty results for missing organic field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])