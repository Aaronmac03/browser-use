#!/usr/bin/env python3
"""
Robust extension downloader with improved error handling and verification.
Addresses CRX download reliability issues mentioned in sep4.md.
"""

import os
import time
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.error
from urllib.parse import urlparse


def log(msg: str, level: str = "INFO"):
    """Simple logging function"""
    print(f"[{level}] {msg}", flush=True)


def verify_crx_format(file_path: Path) -> Tuple[bool, str]:
    """
    Verify that a downloaded file is actually a valid CRX file.
    Returns (is_valid, error_message)
    """
    try:
        if not file_path.exists():
            return False, "File does not exist"
        
        if file_path.stat().st_size < 16:
            return False, f"File too small ({file_path.stat().st_size} bytes)"
        
        with open(file_path, 'rb') as f:
            # Check CRX magic header
            magic = f.read(4)
            if magic != b'Cr24':
                # Check if it's HTML (common when download fails)
                f.seek(0)
                first_bytes = f.read(100).decode('utf-8', errors='ignore').lower()
                if '<html' in first_bytes or '<!doctype' in first_bytes:
                    return False, "Downloaded HTML page instead of CRX file"
                return False, f"Invalid CRX magic header: {magic}"
            
            # Check version
            version = int.from_bytes(f.read(4), 'little')
            if version not in (2, 3):
                return False, f"Unsupported CRX version: {version}"
        
        return True, "Valid CRX file"
        
    except Exception as e:
        return False, f"Error verifying CRX: {e}"


def download_extension_robust(url: str, output_path: Path, max_retries: int = 3, 
                            timeout: int = 30) -> Tuple[bool, str]:
    """
    Download extension with robust error handling and verification.
    
    Args:
        url: Extension download URL
        output_path: Where to save the CRX file
        max_retries: Maximum number of retry attempts
        timeout: Timeout in seconds for each attempt
    
    Returns:
        (success, error_message)
    """
    
    for attempt in range(max_retries):
        try:
            log(f"Downloading extension (attempt {attempt + 1}/{max_retries}): {url}")
            
            # Create request with proper headers
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 
                             'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36')
            request.add_header('Accept', 'application/x-chrome-extension,*/*')
            request.add_header('Accept-Language', 'en-US,en;q=0.9')
            
            # Download with timeout
            with urllib.request.urlopen(request, timeout=timeout) as response:
                # Check response headers
                content_type = response.headers.get('Content-Type', '').lower()
                content_length = response.headers.get('Content-Length')
                
                log(f"Response: {response.status} {response.reason}")
                log(f"Content-Type: {content_type}")
                if content_length:
                    log(f"Content-Length: {content_length} bytes")
                
                # Warn about suspicious content types
                if 'text/html' in content_type:
                    log("WARNING: Server returned HTML content-type", "WARN")
                elif 'application/json' in content_type:
                    log("WARNING: Server returned JSON content-type", "WARN")
                
                # Read response data
                data = response.read()
                
                # Basic size check
                if len(data) < 1000:  # CRX files should be at least 1KB
                    log(f"WARNING: Downloaded file is very small ({len(data)} bytes)", "WARN")
                
                # Write to temporary file first
                temp_path = output_path.with_suffix('.tmp')
                with open(temp_path, 'wb') as f:
                    f.write(data)
                
                # Verify the downloaded file
                is_valid, error_msg = verify_crx_format(temp_path)
                if not is_valid:
                    temp_path.unlink(missing_ok=True)
                    log(f"Downloaded file failed verification: {error_msg}", "ERROR")
                    
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        log(f"Retrying in {wait_time} seconds...", "INFO")
                        time.sleep(wait_time)
                        continue
                    else:
                        return False, f"All attempts failed. Last error: {error_msg}"
                
                # Move temp file to final location
                if output_path.exists():
                    output_path.unlink()
                temp_path.rename(output_path)
                
                # Calculate and log file hash for debugging
                with open(output_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                
                log(f"✅ Successfully downloaded extension ({len(data)} bytes, hash: {file_hash})")
                return True, "Success"
                
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            log(f"HTTP error: {error_msg}", "ERROR")
            
            if e.code in (404, 403):  # Don't retry for these errors
                return False, error_msg
                
        except urllib.error.URLError as e:
            error_msg = f"URL error: {e.reason}"
            log(f"URL error: {error_msg}", "ERROR")
            
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            log(f"Unexpected error: {error_msg}", "ERROR")
        
        # Clean up any partial files
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        temp_path = output_path.with_suffix('.tmp')
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            log(f"Retrying in {wait_time} seconds...", "INFO")
            time.sleep(wait_time)
    
    return False, f"All {max_retries} attempts failed"


def test_extension_download():
    """Test the robust extension downloader"""
    
    # Test with uBlock Origin
    test_url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=133&acceptformat=crx3&x=id%3Dcjpalhdlnbpafiamejdnhcphjbkeiagm%26uc"
    test_path = Path("test_ublock.crx")
    
    log("Testing robust extension download...")
    success, message = download_extension_robust(test_url, test_path)
    
    if success:
        log(f"✅ Test passed: {message}")
        # Clean up
        test_path.unlink(missing_ok=True)
    else:
        log(f"❌ Test failed: {message}")
    
    return success


if __name__ == "__main__":
    test_extension_download()