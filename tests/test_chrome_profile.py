#!/usr/bin/env python3
"""
Test Chrome profile configuration and copying functionality.
Validates profile paths, copying mechanism, and browser startup.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from runner import make_browser, ensure_profile_copy_if_requested


class TestChromeProfile:
    """Test Chrome profile configuration and management."""
    
    def test_chrome_executable_exists(self):
        """Test that Chrome executable exists at configured path."""
        chrome_exe = os.getenv("CHROME_EXECUTABLE")
        if chrome_exe:
            chrome_path = Path(chrome_exe)
            assert chrome_path.exists(), f"Chrome executable not found: {chrome_exe}"
        else:
            # Check common Windows locations
            common_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            
            found = False
            for path in common_paths:
                if Path(path).exists():
                    found = True
                    break
            
            assert found, f"Chrome not found in common locations: {common_paths}"
    
    def test_user_data_directory_exists(self):
        """Test that Chrome user data directory exists."""
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        if user_data_dir:
            user_data_path = Path(user_data_dir)
            assert user_data_path.exists(), f"Chrome user data directory not found: {user_data_dir}"
            
            # Check for Default profile
            profile_dir = os.getenv("CHROME_PROFILE_DIRECTORY", "Default")
            profile_path = user_data_path / profile_dir
            assert profile_path.exists(), f"Chrome profile directory not found: {profile_path}"
        else:
            pytest.skip("CHROME_USER_DATA_DIR not configured")
    
    def test_profile_copy_configuration(self):
        """Test profile copy settings and directory configuration."""
        copy_once = os.getenv("COPY_PROFILE_ONCE", "0")
        copied_dir = os.getenv("COPIED_USER_DATA_DIR")
        
        if copy_once == "1":
            assert copied_dir is not None, "COPIED_USER_DATA_DIR should be set when COPY_PROFILE_ONCE=1"
            
            # Check that parent directory exists or can be created
            copied_path = Path(copied_dir)
            parent_dir = copied_path.parent
            assert parent_dir.exists() or parent_dir == copied_path, f"Parent directory should exist: {parent_dir}"
    
    def test_ensure_profile_copy_if_requested_no_copy(self):
        """Test ensure_profile_copy_if_requested when copying is disabled."""
        with patch.dict(os.environ, {"COPY_PROFILE_ONCE": "0"}):
            user_dir, prof = ensure_profile_copy_if_requested()
            
            # Should return original paths
            expected_user_dir = os.getenv("CHROME_USER_DATA_DIR")
            expected_prof = os.getenv("CHROME_PROFILE_DIRECTORY", "Default")
            
            assert user_dir == expected_user_dir
            assert prof == expected_prof
    
    @patch('shutil.copytree')
    @patch('pathlib.Path.exists')
    def test_ensure_profile_copy_if_requested_with_copy(self, mock_exists, mock_copytree):
        """Test ensure_profile_copy_if_requested when copying is enabled."""
        # Mock that destination doesn't exist (so copying will happen)
        mock_exists.return_value = False
        
        with patch.dict(os.environ, {
            "COPY_PROFILE_ONCE": "1",
            "CHROME_USER_DATA_DIR": "C:\\Users\\test\\AppData\\Local\\Google\\Chrome\\User Data",
            "CHROME_PROFILE_DIRECTORY": "Default",
            "COPIED_USER_DATA_DIR": "E:\\ai\\browser-use\\runtime\\user_data"
        }):
            user_dir, prof = ensure_profile_copy_if_requested()
            
            # Should return copied paths
            assert user_dir == "E:\\ai\\browser-use\\runtime\\user_data"
            assert prof == "Default"
            
            # Should have called copytree
            mock_copytree.assert_called_once()
    
    def test_make_browser_configuration(self):
        """Test make_browser function configuration."""
        # Test without CDP_URL (should create new browser)
        with patch.dict(os.environ, {"CDP_URL": ""}, clear=False):
            with patch('runner.ensure_profile_copy_if_requested') as mock_ensure:
                mock_ensure.return_value = ("test_user_dir", "test_profile")
                
                with patch('runner.Browser') as mock_browser:
                    browser = make_browser()
                    
                    # Should have called Browser constructor with correct args
                    mock_browser.assert_called_once()
                    call_args = mock_browser.call_args
                    
                    assert call_args[1]['user_data_dir'] == "test_user_dir"
                    assert call_args[1]['profile_directory'] == "test_profile"
                    assert call_args[1]['headless'] is False
                    assert call_args[1]['keep_alive'] is True
                    
                    # Check browser args for stability
                    browser_args = call_args[1]['args']
                    assert "--disable-dev-shm-usage" in browser_args
                    assert "--disable-gpu-sandbox" in browser_args
                    assert "--no-first-run" in browser_args
    
    def test_make_browser_with_cdp_url(self):
        """Test make_browser function with CDP_URL set."""
        with patch.dict(os.environ, {"CDP_URL": "http://localhost:9222"}):
            with patch('runner.Browser') as mock_browser:
                browser = make_browser()
                
                # Should have called Browser constructor with CDP URL
                mock_browser.assert_called_once()
                call_args = mock_browser.call_args
                
                assert call_args[1]['cdp_url'] == "http://localhost:9222"
                assert call_args[1]['keep_alive'] is True
    
    def test_browser_args_optimization(self):
        """Test that browser args are optimized for stability."""
        with patch.dict(os.environ, {"CDP_URL": ""}, clear=False):
            with patch('runner.ensure_profile_copy_if_requested') as mock_ensure:
                mock_ensure.return_value = ("test_user_dir", "test_profile")
                
                with patch('runner.Browser') as mock_browser:
                    browser = make_browser()
                    
                    call_args = mock_browser.call_args
                    browser_args = call_args[1]['args']
                    
                    # Check for performance and stability args
                    stability_args = [
                        "--disable-renderer-backgrounding",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-ipc-flooding-protection",
                        "--disable-hang-monitor",
                        "--disable-dev-shm-usage",
                        "--disable-gpu-sandbox"
                    ]
                    
                    for arg in stability_args:
                        assert arg in browser_args, f"Missing stability arg: {arg}"
    
    def test_extensions_configuration(self):
        """Test browser extensions configuration."""
        # Test with extensions disabled (default)
        with patch.dict(os.environ, {"ENABLE_DEFAULT_EXTENSIONS": "0"}, clear=False):
            with patch('runner.ensure_profile_copy_if_requested') as mock_ensure:
                mock_ensure.return_value = ("test_user_dir", "test_profile")
                
                with patch('runner.Browser') as mock_browser:
                    browser = make_browser()
                    
                    call_args = mock_browser.call_args
                    assert call_args[1]['enable_default_extensions'] is False
        
        # Test with extensions enabled
        with patch.dict(os.environ, {"ENABLE_DEFAULT_EXTENSIONS": "1"}, clear=False):
            with patch('runner.ensure_profile_copy_if_requested') as mock_ensure:
                mock_ensure.return_value = ("test_user_dir", "test_profile")
                
                with patch('runner.Browser') as mock_browser:
                    browser = make_browser()
                    
                    call_args = mock_browser.call_args
                    assert call_args[1]['enable_default_extensions'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])