#!/usr/bin/env python3
"""
Configuration validator for browser-use setup.
Validates all required environment variables and dependencies at startup.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import httpx
import asyncio


def log(msg: str, level: str = "INFO"):
    """Simple logging function"""
    print(f"[{level}] {msg}", flush=True)


def check_file_exists(path: str, description: str) -> Tuple[bool, str]:
    """Check if a file exists and is accessible"""
    if not path:
        return False, f"{description}: Path not set"
    
    expanded_path = Path(os.path.expanduser(path))
    if not expanded_path.exists():
        return False, f"{description}: File not found at {expanded_path}"
    
    if not expanded_path.is_file():
        return False, f"{description}: Path exists but is not a file: {expanded_path}"
    
    return True, f"{description}: OK at {expanded_path}"


def check_directory_exists(path: str, description: str) -> Tuple[bool, str]:
    """Check if a directory exists and is accessible"""
    if not path:
        return False, f"{description}: Path not set"
    
    expanded_path = Path(os.path.expanduser(path))
    if not expanded_path.exists():
        return False, f"{description}: Directory not found at {expanded_path}"
    
    if not expanded_path.is_dir():
        return False, f"{description}: Path exists but is not a directory: {expanded_path}"
    
    return True, f"{description}: OK at {expanded_path}"


async def check_http_endpoint(url: str, description: str, timeout: int = 5) -> Tuple[bool, str]:
    """Check if an HTTP endpoint is reachable"""
    if not url:
        return False, f"{description}: URL not set"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            if response.status_code == 200:
                return True, f"{description}: OK (status {response.status_code})"
            else:
                return False, f"{description}: HTTP {response.status_code} at {url}"
    except httpx.TimeoutException:
        return False, f"{description}: Timeout connecting to {url}"
    except Exception as e:
        return False, f"{description}: Error connecting to {url} - {str(e)}"


def check_env_var(var_name: str, description: str, required: bool = True) -> Tuple[bool, str]:
    """Check if an environment variable is set"""
    value = os.getenv(var_name)
    if not value:
        if required:
            return False, f"{description}: {var_name} not set"
        else:
            return True, f"{description}: {var_name} not set (optional)"
    
    return True, f"{description}: {var_name} is set"


async def validate_configuration() -> Tuple[bool, List[str]]:
    """
    Validate all required configuration for browser-use.
    Returns (success, messages)
    """
    results = []
    all_good = True
    
    log("Starting configuration validation...")
    
    # Chrome executable
    chrome_exe = os.getenv("CHROME_EXECUTABLE")
    success, msg = check_file_exists(chrome_exe, "Chrome executable")
    results.append(msg)
    if not success:
        all_good = False
    
    # Chrome user data directory
    user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
    success, msg = check_directory_exists(user_data_dir, "Chrome user data directory")
    results.append(msg)
    if not success:
        all_good = False
    
    # Chrome profile directory (within user data dir)
    if user_data_dir:
        profile_dir = os.getenv("CHROME_PROFILE_DIRECTORY", "Default")
        profile_path = os.path.join(user_data_dir, profile_dir)
        success, msg = check_directory_exists(profile_path, f"Chrome profile '{profile_dir}'")
        results.append(msg)
        if not success:
            all_good = False
    
    # Local LLM server (llama.cpp)
    llamacpp_host = os.getenv("LLAMACPP_HOST", "http://localhost:8080")
    health_url = f"{llamacpp_host.rstrip('/')}/health"
    success, msg = await check_http_endpoint(health_url, "Local LLM server (llama.cpp)")
    results.append(msg)
    if not success:
        log("WARNING: Local LLM server not available. Make sure to start it with start-llama-gpu.bat", "WARN")
    
    # OpenAI API key (for cloud planning)
    success, msg = check_env_var("OPENAI_API_KEY", "OpenAI API key (for cloud planning)")
    results.append(msg)
    if not success:
        all_good = False
    
    # Google API key (Gemini fallback)
    success, msg = check_env_var("GOOGLE_API_KEY", "Google API key (Gemini fallback)")
    results.append(msg)
    if not success:
        log("WARNING: Google API key not set. Gemini fallback won't work.", "WARN")
    
    # Serper API key (optional but recommended)
    success, msg = check_env_var("SERPER_API_KEY", "Serper API key (web search)", required=False)
    results.append(msg)
    if not success:
        log("INFO: Serper API key not set. Web search tool won't work.", "INFO")
    
    # Browser startup timeout
    timeout_str = os.getenv("BROWSER_START_TIMEOUT_SEC", "30")
    try:
        timeout_val = float(timeout_str)
        if timeout_val < 30:
            results.append(f"Browser startup timeout: {timeout_val}s (consider increasing to 60s+ for stability)")
        else:
            results.append(f"Browser startup timeout: {timeout_val}s (OK)")
    except ValueError:
        results.append(f"Browser startup timeout: Invalid value '{timeout_str}' (should be a number)")
        all_good = False
    
    # Extension settings
    enable_ext = os.getenv("ENABLE_DEFAULT_EXTENSIONS", "0")
    if enable_ext.lower() in ("1", "true", "yes"):
        results.append("Default extensions: ENABLED (may cause CRX download issues)")
        log("INFO: Extensions enabled. If you see CRX errors, set ENABLE_DEFAULT_EXTENSIONS=0", "INFO")
    else:
        results.append("Default extensions: DISABLED (recommended for stability)")
    
    # Profile copy settings
    copy_profile = os.getenv("COPY_PROFILE_ONCE", "0")
    if copy_profile == "1":
        copied_dir = os.getenv("COPIED_USER_DATA_DIR", "./runtime/user_data")
        success, msg = check_directory_exists(os.path.dirname(copied_dir), "Copied profile parent directory")
        results.append(f"Profile copy: ENABLED -> {copied_dir}")
        if not success:
            results.append(f"Profile copy directory issue: {msg}")
    else:
        results.append("Profile copy: DISABLED (using system profile directly)")
    
    return all_good, results


async def main():
    """Main validation function"""
    try:
        success, messages = await validate_configuration()
        
        log("Configuration validation results:")
        for msg in messages:
            print(f"  • {msg}")
        
        if success:
            log("✅ Configuration validation PASSED", "SUCCESS")
            return 0
        else:
            log("❌ Configuration validation FAILED", "ERROR")
            log("Please fix the issues above before running browser-use", "ERROR")
            return 1
            
    except Exception as e:
        log(f"Configuration validation error: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run validation
    exit_code = asyncio.run(main())
    sys.exit(exit_code)