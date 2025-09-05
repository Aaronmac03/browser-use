#!/usr/bin/env python3
"""
Chrome Process Cleanup Utility for browser-use

This script helps resolve Chrome process conflicts that can cause CDP connection issues.
Safely terminates existing Chrome processes and cleans up locked profiles.
"""

import subprocess
import psutil
import time
import os
from pathlib import Path


def log(msg: str, level: str = "INFO"):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


def find_chrome_processes():
    """Find all Chrome processes using psutil for cross-platform compatibility"""
    chrome_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower()
            if 'chrome' in name and proc.info['cmdline']:
                chrome_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': proc.info['cmdline']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return chrome_processes


def terminate_chrome_processes(force: bool = False):
    """Terminate Chrome processes safely"""
    processes = find_chrome_processes()
    
    if not processes:
        log("No Chrome processes found")
        return True
    
    log(f"Found {len(processes)} Chrome processes")
    
    terminated = []
    for proc_info in processes:
        try:
            proc = psutil.Process(proc_info['pid'])
            
            # Check if this is a CDP-enabled Chrome instance
            cmdline = ' '.join(proc_info.get('cmdline', []))
            is_debugging = '--remote-debugging-port' in cmdline
            
            if is_debugging:
                log(f"Terminating Chrome debugging process PID {proc_info['pid']}")
            else:
                log(f"Terminating Chrome process PID {proc_info['pid']}")
            
            if force:
                proc.kill()
            else:
                proc.terminate()
                
            terminated.append(proc_info['pid'])
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            log(f"Could not terminate PID {proc_info['pid']}: {e}", "WARN")
    
    if terminated:
        log("Waiting for processes to terminate...")
        time.sleep(2)
        
        # Check if any processes are still running
        still_running = []
        for pid in terminated:
            try:
                if psutil.Process(pid).is_running():
                    still_running.append(pid)
            except psutil.NoSuchProcess:
                pass
        
        if still_running:
            log(f"Force killing {len(still_running)} remaining processes")
            for pid in still_running:
                try:
                    psutil.Process(pid).kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    
    log("Chrome process cleanup completed")
    return True


def cleanup_profile_locks(user_data_dir: str = None):
    """Remove Chrome profile lock files"""
    if not user_data_dir:
        # Common Chrome profile locations
        common_paths = [
            os.path.expanduser("~/.config/google-chrome"),
            os.path.expanduser("~/Library/Application Support/Google/Chrome"),
            os.path.expanduser("~/AppData/Local/Google/Chrome/User Data"),
        ]
        
        for path in common_paths:
            if Path(path).exists():
                user_data_dir = path
                break
    
    if not user_data_dir or not Path(user_data_dir).exists():
        log("No Chrome user data directory found to clean")
        return
    
    log(f"Cleaning profile locks in {user_data_dir}")
    
    lock_files = [
        "SingletonLock",
        "lockfile",
        "Singleton",
        "Default/Singleton",
        "Profile 1/Singleton",
    ]
    
    cleaned = 0
    for lock_file in lock_files:
        lock_path = Path(user_data_dir) / lock_file
        if lock_path.exists():
            try:
                lock_path.unlink()
                log(f"Removed lock file: {lock_file}")
                cleaned += 1
            except OSError as e:
                log(f"Could not remove {lock_file}: {e}", "WARN")
    
    if cleaned > 0:
        log(f"Cleaned {cleaned} profile lock files")
    else:
        log("No profile lock files found to clean")


def check_debug_ports():
    """Check for active Chrome debugging ports"""
    debug_ports = []
    
    try:
        if os.name == 'nt':  # Windows
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
                                    if 9000 <= port_num <= 9999:
                                        debug_ports.append(port_num)
                                except ValueError:
                                    pass
        else:  # Unix-like
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '127.0.0.1:' in line:
                        parts = line.split()
                        for part in parts:
                            if part.startswith('127.0.0.1:'):
                                port = part.split(':')[1]
                                try:
                                    port_num = int(port)
                                    if 9000 <= port_num <= 9999:
                                        debug_ports.append(port_num)
                                except ValueError:
                                    pass
    except Exception as e:
        log(f"Could not check debug ports: {e}", "WARN")
    
    debug_ports = sorted(set(debug_ports))
    if debug_ports:
        log(f"Active Chrome debugging ports: {debug_ports}")
    else:
        log("No active Chrome debugging ports found")
    
    return debug_ports


def main():
    """Main cleanup function"""
    log("Starting Chrome process cleanup...")
    log("This will terminate all Chrome processes and clean profile locks")
    
    # Show current state
    processes = find_chrome_processes()
    debug_ports = check_debug_ports()
    
    if not processes and not debug_ports:
        log("No Chrome processes or debug ports active - cleanup not needed")
        return 0
    
    try:
        # Terminate Chrome processes
        terminate_chrome_processes()
        
        # Clean profile locks
        cleanup_profile_locks()
        
        # Wait a moment and verify cleanup
        time.sleep(1)
        remaining_processes = find_chrome_processes()
        remaining_ports = check_debug_ports()
        
        if remaining_processes:
            log(f"WARNING: {len(remaining_processes)} Chrome processes still running", "WARN")
            return 1
        
        if remaining_ports:
            log(f"WARNING: Debug ports still active: {remaining_ports}", "WARN")
            return 1
        
        log("Chrome cleanup completed successfully")
        return 0
        
    except Exception as e:
        log(f"Cleanup failed: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)