#!/usr/bin/env python3
"""
Setup script for llama.cpp server with Moondream2 GGUF
Replaces setup_ollama.py for Browser-Use local vision capabilities
"""

import asyncio
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional

from llama_cpp_manager import LlamaCppManager


def print_header():
	"""Print setup header."""
	print("=" * 60)
	print("Browser-Use llama.cpp Server Setup")
	print("Setting up Moondream2 GGUF for local vision analysis")
	print("=" * 60)


def check_dependencies() -> List[str]:
	"""Check for required dependencies."""
	missing = []
	
	# Check for build tools
	try:
		subprocess.run(["make", "--version"], check=True, capture_output=True)
	except (subprocess.CalledProcessError, FileNotFoundError):
		missing.append("build tools (make)")
	
	# Check for git
	try:
		subprocess.run(["git", "--version"], check=True, capture_output=True)
	except (subprocess.CalledProcessError, FileNotFoundError):
		missing.append("git")
	
	# Check for wget or curl
	has_downloader = False
	for cmd in ["wget", "curl"]:
		try:
			subprocess.run([cmd, "--version"], check=True, capture_output=True)
			has_downloader = True
			break
		except (subprocess.CalledProcessError, FileNotFoundError):
			pass
	
	if not has_downloader:
		missing.append("wget or curl (for downloading models)")
	
	return missing


def install_dependencies_linux():
	"""Install dependencies on Linux."""
	print("Installing dependencies on Linux...")
	try:
		# Try different package managers
		for pm in [
			["sudo", "apt-get", "update", "&&", "sudo", "apt-get", "install", "-y", "build-essential", "git", "wget"],
			["sudo", "yum", "install", "-y", "gcc", "gcc-c++", "make", "git", "wget"],
			["sudo", "pacman", "-S", "--noconfirm", "base-devel", "git", "wget"],
		]:
			try:
				subprocess.run(" ".join(pm), shell=True, check=True)
				return True
			except subprocess.CalledProcessError:
				continue
		
		print("❌ Could not install dependencies automatically")
		print("Please install build-essential, git, and wget manually")
		return False
	except Exception as e:
		print(f"❌ Dependency installation failed: {e}")
		return False


def install_dependencies_macos():
	"""Install dependencies on macOS."""
	print("Installing dependencies on macOS...")
	try:
		# Check for Xcode command line tools
		subprocess.run(["xcode-select", "--install"], check=True, capture_output=True)
		
		# Try to install wget via Homebrew
		try:
			subprocess.run(["brew", "install", "wget"], check=True, capture_output=True)
		except (subprocess.CalledProcessError, FileNotFoundError):
			print("Note: Homebrew not found or failed. You may need to install wget manually")
		
		return True
	except subprocess.CalledProcessError:
		print("❌ Xcode command line tools installation failed")
		return False


def compile_llama_cpp() -> Optional[str]:
	"""Compile llama.cpp from source."""
	llama_dir = Path("./llama.cpp")
	
	print("📦 Downloading and compiling llama.cpp...")
	
	try:
		# Clone if not exists
		if not llama_dir.exists():
			print("Cloning llama.cpp repository...")
			subprocess.run([
				"git", "clone", "https://github.com/ggerganov/llama.cpp.git"
			], check=True)
		
		# Build
		print("Compiling llama.cpp (this may take a few minutes)...")
		os.chdir(llama_dir)
		
		# Use appropriate make command
		make_cmd = ["make", "-j"]
		if platform.system() == "Darwin":  # macOS
			make_cmd = ["make", "-j", "LLAMA_METAL=1"]  # Enable Metal acceleration
		
		subprocess.run(make_cmd, check=True)
		
		# Check if server binary exists
		server_path = llama_dir / "llama-server"
		if not server_path.exists():
			server_path = llama_dir / "server"  # Older builds
		
		if server_path.exists():
			print(f"✅ llama.cpp compiled successfully: {server_path.absolute()}")
			os.chdir("..")
			return str(server_path.absolute())
		else:
			print("❌ llama-server binary not found after compilation")
			os.chdir("..")
			return None
			
	except subprocess.CalledProcessError as e:
		print(f"❌ Compilation failed: {e}")
		if llama_dir.exists():
			os.chdir("..")
		return None
	except Exception as e:
		print(f"❌ Unexpected error during compilation: {e}")
		if llama_dir.exists():
			os.chdir("..")
		return None


def download_moondream2_model() -> Optional[str]:
	"""Download Moondream2 GGUF model."""
	models_dir = Path("./models")
	models_dir.mkdir(exist_ok=True)
	
	model_path = models_dir / "moondream2-q4_k_m.gguf"
	
	if model_path.exists():
		print(f"✅ Moondream2 model already exists: {model_path}")
		return str(model_path)
	
	print("📥 Downloading Moondream2 GGUF model (this may take several minutes)...")
	
	# Try multiple model sources
	model_urls = [
		"https://huggingface.co/bartowski/moondream2-GGUF/resolve/main/moondream2-q4_k_m.gguf",
		"https://huggingface.co/second-state/Moondream2-GGUF/resolve/main/moondream2-q4_k_m.gguf",
	]
	
	for url in model_urls:
		try:
			print(f"Trying to download from: {url}")
			
			# Use wget if available, otherwise urllib
			try:
				subprocess.run([
					"wget", "-O", str(model_path), url
				], check=True)
				break
			except (subprocess.CalledProcessError, FileNotFoundError):
				# Fallback to curl
				try:
					subprocess.run([
						"curl", "-L", "-o", str(model_path), url
					], check=True)
					break
				except (subprocess.CalledProcessError, FileNotFoundError):
					# Fallback to urllib
					print("Using urllib for download (may be slower)...")
					urllib.request.urlretrieve(url, model_path)
					break
					
		except Exception as e:
			print(f"Download failed from {url}: {e}")
			if model_path.exists():
				model_path.unlink()  # Remove partial file
			continue
	
	if model_path.exists() and model_path.stat().st_size > 1024 * 1024:  # At least 1MB
		print(f"✅ Moondream2 model downloaded: {model_path}")
		return str(model_path)
	else:
		print("❌ Failed to download Moondream2 model")
		return None


async def test_setup(server_path: str, model_path: str) -> bool:
	"""Test the complete setup."""
	print("🧪 Testing llama.cpp server with Moondream2...")
	
	# Create manager
	manager = LlamaCppManager(model_path=model_path)
	
	# Start server
	print("Starting server...")
	if not manager.start_server():
		print("❌ Failed to start server")
		return False
	
	# Wait for server to be ready
	await asyncio.sleep(5)
	
	# Test vision capability
	result = await manager.test_vision_capability()
	
	# Stop server
	manager.stop_server()
	
	if result.get("success"):
		print(f"✅ Vision test successful: {result['description'][:100]}...")
		return True
	else:
		print(f"❌ Vision test failed: {result.get('error', 'Unknown error')}")
		return False


def create_run_script(server_path: str, model_path: str):
	"""Create a convenient run script."""
	script_content = f"""#!/bin/bash
# llama.cpp server startup script for Browser-Use
# Generated by setup_llamacpp.py

echo "Starting llama.cpp server with Moondream2..."
echo "Server will be available at http://localhost:8080"
echo "Press Ctrl+C to stop the server"

{server_path} \\
    -m "{model_path}" \\
    --host 0.0.0.0 \\
    --port 8080 \\
    --ctx-size 2048 \\
    --threads {os.cpu_count() or 4} \\
    --mlock \\
    --log-format json \\
    --verbose
"""
	
	script_path = Path("./run_llamacpp_server.sh")
	with open(script_path, "w") as f:
		f.write(script_content)
	
	# Make executable
	os.chmod(script_path, 0o755)
	
	print(f"✅ Created run script: {script_path.absolute()}")
	print("   Use './run_llamacpp_server.sh' to start the server")


async def main():
	"""Main setup function."""
	print_header()
	
	# Check current platform
	current_os = platform.system()
	print(f"Detected OS: {current_os}")
	
	# Check dependencies
	missing_deps = check_dependencies()
	if missing_deps:
		print(f"Missing dependencies: {', '.join(missing_deps)}")
		
		if current_os == "Linux":
			if not install_dependencies_linux():
				sys.exit(1)
		elif current_os == "Darwin":
			if not install_dependencies_macos():
				sys.exit(1)
		else:
			print("Please install the missing dependencies manually")
			sys.exit(1)
	
	# Compile llama.cpp
	server_path = compile_llama_cpp()
	if not server_path:
		print("❌ Failed to compile llama.cpp")
		sys.exit(1)
	
	# Download model
	model_path = download_moondream2_model()
	if not model_path:
		print("❌ Failed to download Moondream2 model")
		sys.exit(1)
	
	# Test setup
	if await test_setup(server_path, model_path):
		print("✅ Setup completed successfully!")
		
		# Create convenience script
		create_run_script(server_path, model_path)
		
		print("\n" + "=" * 60)
		print("Setup Complete! 🎉")
		print("=" * 60)
		print(f"Server executable: {server_path}")
		print(f"Model file: {model_path}")
		print("Quick start: ./run_llamacpp_server.sh")
		print("\nTo use in Python:")
		print("from browser_use.llm import ChatLlamaCpp")
		print("llm = ChatLlamaCpp(model='moondream2')")
		print("=" * 60)
	else:
		print("❌ Setup test failed")
		sys.exit(1)


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print("\n❌ Setup interrupted by user")
		sys.exit(1)
	except Exception as e:
		print(f"❌ Setup failed with error: {e}")
		sys.exit(1)