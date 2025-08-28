#!/usr/bin/env python3
"""
Test runner script for browser-agent project.

This script provides an easy way to run different types of tests with various options.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False


def setup_test_environment():
    """Set up the test environment."""
    print("Setting up test environment...")
    
    # Create necessary directories
    dirs = ["logs", "screenshots", "downloads", "cache", "profiles"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
    
    # Set environment variables
    os.environ["BROWSER_AGENT_MASTER_PASSWORD"] = "test_password"
    os.environ["HEADLESS"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    print("Test environment set up successfully!")


def run_unit_tests(coverage=True, verbose=True):
    """Run unit tests."""
    print("Running unit tests...")
    
    cmd = ["pytest", "tests/"]
    cmd.extend(["-m", "not integration and not security and not slow"])
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["--junit-xml=test-results-unit.xml"])
    
    return run_command(cmd)


def run_integration_tests(verbose=True):
    """Run integration tests."""
    print("Running integration tests...")
    
    cmd = ["pytest", "tests/"]
    cmd.extend(["-m", "integration"])
    cmd.extend(["--timeout=300"])
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["--junit-xml=test-results-integration.xml"])
    
    return run_command(cmd)


def run_security_tests(verbose=True):
    """Run security tests."""
    print("Running security tests...")
    
    cmd = ["pytest", "tests/"]
    cmd.extend(["-m", "security"])
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["--junit-xml=test-results-security.xml"])
    
    return run_command(cmd)


def run_performance_tests(verbose=True):
    """Run performance tests."""
    print("Running performance tests...")
    
    cmd = ["pytest", "tests/"]
    cmd.extend(["-m", "performance"])
    cmd.extend(["--benchmark-only"])
    
    if verbose:
        cmd.append("-v")
    
    return run_command(cmd)


def run_all_tests(coverage=True, verbose=True):
    """Run all tests."""
    print("Running all tests...")
    
    cmd = ["pytest", "tests/"]
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["--junit-xml=test-results-all.xml"])
    
    return run_command(cmd)


def run_specific_test(test_path, verbose=True):
    """Run a specific test file or test function."""
    print(f"Running specific test: {test_path}")
    
    cmd = ["pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    return run_command(cmd)


def run_linting():
    """Run code linting and formatting checks."""
    print("Running linting checks...")
    
    success = True
    
    # Check if tools are installed
    tools = ["black", "isort", "flake8"]
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"Installing {tool}...")
            if not run_command(["pip", "install", tool]):
                success = False
                continue
    
    # Run black formatting check
    print("Checking code formatting with black...")
    if not run_command(["black", "--check", "--diff", "."]):
        success = False
    
    # Run isort import sorting check
    print("Checking import sorting with isort...")
    if not run_command(["isort", "--check-only", "--diff", "."]):
        success = False
    
    # Run flake8 linting
    print("Running flake8 linting...")
    if not run_command(["flake8", ".", "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"]):
        success = False
    
    return success


def run_security_scan():
    """Run security vulnerability scanning."""
    print("Running security scans...")
    
    success = True
    
    # Install security tools if needed
    tools = ["bandit", "safety"]
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"Installing {tool}...")
            if not run_command(["pip", "install", tool]):
                success = False
                continue
    
    # Run bandit security scan
    print("Running bandit security scan...")
    if not run_command(["bandit", "-r", ".", "-f", "json", "-o", "bandit-report.json"]):
        print("Bandit found security issues (check bandit-report.json)")
        # Don't fail on bandit issues, just warn
    
    # Run safety dependency check
    print("Running safety dependency check...")
    if not run_command(["safety", "check", "--json", "--output", "safety-report.json"]):
        print("Safety found vulnerable dependencies (check safety-report.json)")
        # Don't fail on safety issues, just warn
    
    return success


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test runner for browser-agent project")
    parser.add_argument("--type", choices=["unit", "integration", "security", "performance", "all"], 
                       default="unit", help="Type of tests to run")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage reporting")
    parser.add_argument("--quiet", action="store_true", help="Run tests in quiet mode")
    parser.add_argument("--lint", action="store_true", help="Run linting checks")
    parser.add_argument("--security-scan", action="store_true", help="Run security scans")
    parser.add_argument("--test", help="Run specific test file or function")
    parser.add_argument("--setup-only", action="store_true", help="Only set up test environment")
    
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Set up test environment
    setup_test_environment()
    
    if args.setup_only:
        print("Test environment setup complete!")
        return 0
    
    success = True
    
    # Run linting if requested
    if args.lint:
        if not run_linting():
            success = False
    
    # Run security scan if requested
    if args.security_scan:
        if not run_security_scan():
            success = False
    
    # Run specific test if provided
    if args.test:
        if not run_specific_test(args.test, verbose=not args.quiet):
            success = False
    else:
        # Run tests based on type
        coverage = not args.no_coverage
        verbose = not args.quiet
        
        if args.type == "unit":
            if not run_unit_tests(coverage=coverage, verbose=verbose):
                success = False
        elif args.type == "integration":
            if not run_integration_tests(verbose=verbose):
                success = False
        elif args.type == "security":
            if not run_security_tests(verbose=verbose):
                success = False
        elif args.type == "performance":
            if not run_performance_tests(verbose=verbose):
                success = False
        elif args.type == "all":
            if not run_all_tests(coverage=coverage, verbose=verbose):
                success = False
    
    if success:
        print("\n✅ All tests completed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())