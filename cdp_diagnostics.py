#!/usr/bin/env python3
"""
CDP readiness diagnostics for browser-use.
Helps diagnose browser startup and CDP connection issues.
"""

import asyncio
import time
import json
from typing import Optional, Dict, Any
import aiohttp
from pathlib import Path
import subprocess
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()


def log(msg: str, level: str = "INFO"):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


async def check_cdp_endpoint(port: int, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Check CDP endpoint and return detailed information.
    """
    base_url = f"http://localhost:{port}"
    endpoints = {
        "version": "/json/version",
        "list": "/json/list", 
        "new": "/json/new"
    }
    
    results = {
        "port": port,
        "base_url": base_url,
        "accessible": False,
        "endpoints": {},
        "error": None,
        "response_time": None
    }
    
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            # Check version endpoint first (most reliable)
            try:
                async with session.get(f"{base_url}/json/version") as resp:
                    response_time = time.time() - start_time
                    results["response_time"] = response_time
                    results["accessible"] = True
                    
                    if resp.status == 200:
                        version_data = await resp.json()
                        results["endpoints"]["version"] = {
                            "status": resp.status,
                            "data": version_data
                        }
                        log(f"CDP version endpoint OK ({response_time:.3f}s): {version_data.get('Browser', 'Unknown')}")
                    else:
                        results["endpoints"]["version"] = {
                            "status": resp.status,
                            "error": f"HTTP {resp.status}"
                        }
                        log(f"CDP version endpoint returned {resp.status}", "WARN")
                        
            except Exception as e:
                results["endpoints"]["version"] = {"error": str(e)}
                log(f"CDP version endpoint failed: {e}", "ERROR")
            
            # Check other endpoints if version worked
            if results["accessible"]:
                for name, path in [("list", "/json/list"), ("new", "/json/new")]:
                    try:
                        async with session.get(f"{base_url}{path}") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                results["endpoints"][name] = {
                                    "status": resp.status,
                                    "data": data
                                }
                            else:
                                results["endpoints"][name] = {
                                    "status": resp.status,
                                    "error": f"HTTP {resp.status}"
                                }
                    except Exception as e:
                        results["endpoints"][name] = {"error": str(e)}
                        
    except Exception as e:
        results["error"] = str(e)
        results["response_time"] = time.time() - start_time
        log(f"CDP connection failed after {results['response_time']:.3f}s: {e}", "ERROR")
    
    return results


def find_chrome_processes() -> list:
    """Find running Chrome processes"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                processes = []
                for line in lines:
                    if line.strip():
                        parts = [p.strip('"') for p in line.split('","')]
                        if len(parts) >= 2:
                            processes.append({
                                "name": parts[0],
                                "pid": parts[1],
                                "memory": parts[4] if len(parts) > 4 else "Unknown"
                            })
                return processes
        else:  # Unix-like
            result = subprocess.run(['pgrep', '-f', 'chrome'], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                return [{"pid": pid.strip()} for pid in pids if pid.strip()]
    except Exception as e:
        log(f"Error finding Chrome processes: {e}", "WARN")
    
    return []


def find_chrome_debug_ports() -> list:
    """Find Chrome processes with debug ports"""
    debug_ports = []
    
    try:
        if os.name == 'nt':  # Windows
            # Use netstat to find listening ports
            result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'LISTENING' in line and '127.0.0.1:' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            addr = parts[1]
                            if addr.startswith('127.0.0.1:'):
                                port = addr.split(':')[1]
                                try:
                                    port_num = int(port)
                                    if 9000 <= port_num <= 9999:  # Common Chrome debug port range
                                        debug_ports.append(port_num)
                                except ValueError:
                                    pass
    except Exception as e:
        log(f"Error finding debug ports: {e}", "WARN")
    
    return sorted(set(debug_ports))


async def diagnose_browser_startup(chrome_exe: Optional[str] = None, 
                                 user_data_dir: Optional[str] = None,
                                 timeout: float = 60.0) -> Dict[str, Any]:
    """
    Comprehensive browser startup diagnostics.
    """
    log("Starting browser startup diagnostics...")
    
    # Get configuration
    chrome_exe = chrome_exe or os.getenv("CHROME_EXECUTABLE")
    user_data_dir = user_data_dir or os.getenv("CHROME_USER_DATA_DIR")
    
    results = {
        "config": {
            "chrome_exe": chrome_exe,
            "user_data_dir": user_data_dir,
            "timeout": timeout
        },
        "pre_startup": {},
        "startup": {},
        "post_startup": {}
    }
    
    # Pre-startup checks
    log("=== Pre-startup checks ===")
    
    # Check Chrome executable
    if chrome_exe and Path(chrome_exe).exists():
        results["pre_startup"]["chrome_exe_exists"] = True
        log(f"✅ Chrome executable found: {chrome_exe}")
    else:
        results["pre_startup"]["chrome_exe_exists"] = False
        log(f"❌ Chrome executable not found: {chrome_exe}", "ERROR")
    
    # Check user data directory
    if user_data_dir and Path(user_data_dir).exists():
        results["pre_startup"]["user_data_dir_exists"] = True
        log(f"✅ User data directory found: {user_data_dir}")
    else:
        results["pre_startup"]["user_data_dir_exists"] = False
        log(f"❌ User data directory not found: {user_data_dir}", "ERROR")
    
    # Check existing Chrome processes
    existing_processes = find_chrome_processes()
    results["pre_startup"]["existing_processes"] = len(existing_processes)
    if existing_processes:
        log(f"⚠️ Found {len(existing_processes)} existing Chrome processes", "WARN")
        for proc in existing_processes[:3]:  # Show first 3
            log(f"  - PID {proc['pid']}: {proc.get('memory', 'Unknown')} memory")
    else:
        log("✅ No existing Chrome processes found")
    
    # Check existing debug ports
    existing_ports = find_chrome_debug_ports()
    results["pre_startup"]["existing_debug_ports"] = existing_ports
    if existing_ports:
        log(f"⚠️ Found existing debug ports: {existing_ports}", "WARN")
    else:
        log("✅ No existing debug ports found")
    
    # Startup simulation (if Chrome exe exists)
    if chrome_exe and Path(chrome_exe).exists():
        log("=== Simulating browser startup ===")
        
        # Find free port
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            s.listen(1)
            debug_port = s.getsockname()[1]
        
        log(f"Using debug port: {debug_port}")
        
        # Build Chrome command
        cmd = [
            chrome_exe,
            f"--remote-debugging-port={debug_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-translate",
            "--headless=new"  # Use new headless mode for testing
        ]
        
        if user_data_dir:
            cmd.append(f"--user-data-dir={user_data_dir}")
        
        log(f"Starting Chrome with command: {' '.join(cmd[:3])}...")
        
        startup_start = time.time()
        process = None
        
        try:
            # Start Chrome process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True)
            
            results["startup"]["process_started"] = True
            results["startup"]["pid"] = process.pid
            log(f"✅ Chrome process started (PID: {process.pid})")
            
            # Wait for CDP to become available
            log("Waiting for CDP to become available...")
            cdp_ready = False
            cdp_results = None
            
            for attempt in range(int(timeout)):
                await asyncio.sleep(1)
                elapsed = time.time() - startup_start
                
                cdp_results = await check_cdp_endpoint(debug_port, timeout=2.0)
                if cdp_results["accessible"]:
                    cdp_ready = True
                    log(f"✅ CDP ready after {elapsed:.1f}s")
                    break
                
                if attempt % 10 == 0:  # Log every 10 seconds
                    log(f"Still waiting for CDP... ({elapsed:.1f}s elapsed)")
                
                # Check if process is still running
                if process.poll() is not None:
                    log("❌ Chrome process terminated unexpectedly", "ERROR")
                    break
            
            results["startup"]["cdp_ready"] = cdp_ready
            results["startup"]["cdp_ready_time"] = time.time() - startup_start
            results["startup"]["cdp_results"] = cdp_results
            
            if not cdp_ready:
                log(f"❌ CDP not ready after {timeout}s timeout", "ERROR")
            
        except Exception as e:
            results["startup"]["error"] = str(e)
            log(f"❌ Error during startup: {e}", "ERROR")
        
        finally:
            # Clean up process
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    log("✅ Chrome process terminated")
                except Exception as e:
                    log(f"⚠️ Error terminating Chrome: {e}", "WARN")
                    try:
                        process.kill()
                    except:
                        pass
    
    # Post-startup summary
    log("=== Diagnostic Summary ===")
    
    if results.get("startup", {}).get("cdp_ready"):
        ready_time = results["startup"]["cdp_ready_time"]
        log(f"✅ Browser startup successful ({ready_time:.1f}s)")
        
        if ready_time > 30:
            log("⚠️ Startup time is slow. Consider:", "WARN")
            log("  - Increasing BROWSER_START_TIMEOUT_SEC")
            log("  - Disabling extensions (ENABLE_DEFAULT_EXTENSIONS=0)")
            log("  - Using profile copy (COPY_PROFILE_ONCE=1)")
    else:
        log("❌ Browser startup failed or timed out", "ERROR")
        log("Recommendations:")
        log("  - Check Chrome executable path")
        log("  - Check user data directory permissions")
        log("  - Try with a clean profile")
        log("  - Check antivirus/firewall settings")
    
    return results


async def main():
    """Main diagnostic function"""
    try:
        results = await diagnose_browser_startup()
        
        # Save results to file
        results_file = Path("cdp_diagnostics_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        log(f"Diagnostic results saved to: {results_file}")
        
        return 0 if results.get("startup", {}).get("cdp_ready") else 1
        
    except Exception as e:
        log(f"Diagnostic error: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)