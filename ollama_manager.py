#!/usr/bin/env python3
"""
Ollama Service Manager for Browser-Use Hybrid Agent
Handles Ollama installation, startup, model management, and health checks
"""

import asyncio
import subprocess
import sys
import time
import httpx
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import platform

class OllamaManager:
	"""Manages Ollama service lifecycle and model availability."""
	
	def __init__(self, endpoint: str = "http://localhost:11434", model: str = "moondream:latest"):
		self.endpoint = endpoint
		self.model = model
		self.required_models = [model]
		
	async def check_ollama_installation(self) -> bool:
		"""Check if ollama command is available."""
		try:
			result = subprocess.run(
				["ollama", "--version"], 
				capture_output=True, 
				text=True, 
				timeout=10
			)
			if result.returncode == 0:
				print(f"✅ Ollama installed: {result.stdout.strip()}")
				return True
			return False
		except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
			return False
	
	def install_ollama(self) -> bool:
		"""Install Ollama if not present."""
		system = platform.system().lower()
		
		print("🔽 Ollama not found. Installing...")
		
		if system == "windows":
			print("📋 Windows detected:")
			print("1. Download from: https://ollama.ai/download")
			print("2. Or use winget: winget install Ollama.Ollama")
			print("3. Restart terminal after installation")
			
		elif system == "darwin":  # macOS
			print("📋 macOS detected:")
			print("1. Download from: https://ollama.ai/download")
			print("2. Or use brew: brew install ollama")
			
		elif system == "linux":
			try:
				print("🐧 Linux detected, attempting automatic installation...")
				result = subprocess.run([
					"curl", "-fsSL", "https://ollama.ai/install.sh"
				], capture_output=True, text=True, check=True)
				
				install_script = result.stdout
				proc = subprocess.run([
					"sh", "-c", install_script
				], capture_output=True, text=True)
				
				if proc.returncode == 0:
					print("✅ Ollama installed successfully")
					return True
				else:
					print(f"❌ Installation failed: {proc.stderr}")
					
			except subprocess.CalledProcessError as e:
				print(f"❌ Failed to download installer: {e}")
				print("📋 Manual installation:")
				print("curl -fsSL https://ollama.ai/install.sh | sh")
				
		print("\n🔄 Please restart your terminal and run the script again.")
		return False
	
	async def check_service_running(self) -> bool:
		"""Check if Ollama service is running."""
		try:
			timeout_config = httpx.Timeout(connect=3.0, read=10.0)
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				response = await client.get(f"{self.endpoint}/api/version")
				if response.status_code == 200:
					version_info = response.json()
					print(f"✅ Ollama service running: {version_info.get('version', 'unknown')}")
					return True
				return False
		except Exception as e:
			print(f"❌ Ollama service not responding: {type(e).__name__}")
			return False
	
	def start_ollama_service(self) -> bool:
		"""Start Ollama service."""
		try:
			print("🚀 Starting Ollama service...")
			
			# Try to start as a background service
			if platform.system().lower() == "windows":
				# On Windows, try starting the service
				subprocess.Popen(
					["ollama", "serve"], 
					creationflags=subprocess.CREATE_NEW_CONSOLE,
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL
				)
			else:
				# On Unix-like systems
				subprocess.Popen(
					["ollama", "serve"], 
					stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL,
					start_new_session=True
				)
			
			print("⏳ Waiting for service to start...")
			time.sleep(3)  # Give it time to start
			return True
			
		except Exception as e:
			print(f"❌ Failed to start Ollama service: {e}")
			print("💡 Try running manually: ollama serve")
			return False
	
	async def list_models(self) -> List[Dict[str, Any]]:
		"""List available models."""
		try:
			timeout_config = httpx.Timeout(connect=3.0, read=30.0)
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				response = await client.get(f"{self.endpoint}/api/tags")
				if response.status_code == 200:
					data = response.json()
					return data.get('models', [])
				return []
		except Exception as e:
			print(f"❌ Failed to list models: {e}")
			return []
	
	def pull_model(self, model_name: str) -> bool:
		"""Pull a model from Ollama registry."""
		try:
			print(f"🔽 Pulling model: {model_name}")
			print("⏳ This may take several minutes for large models...")
			
			result = subprocess.run(
				["ollama", "pull", model_name],
				text=True,
				timeout=1800  # 30 minutes timeout
			)
			
			if result.returncode == 0:
				print(f"✅ Model {model_name} pulled successfully")
				return True
			else:
				print(f"❌ Failed to pull model {model_name}")
				return False
				
		except subprocess.TimeoutExpired:
			print(f"⏰ Timeout pulling model {model_name}")
			return False
		except Exception as e:
			print(f"❌ Error pulling model {model_name}: {e}")
			return False
	
	def remove_old_models(self, models_to_remove: List[str]) -> None:
		"""Remove old models to free space."""
		for model in models_to_remove:
			try:
				print(f"🗑️  Removing old model: {model}")
				result = subprocess.run(
					["ollama", "rm", model],
					capture_output=True,
					text=True,
					timeout=60
				)
				if result.returncode == 0:
					print(f"✅ Removed {model}")
				else:
					print(f"⚠️  Could not remove {model}: {result.stderr}")
			except Exception as e:
				print(f"❌ Error removing {model}: {e}")
	
	async def ensure_model_available(self, model_name: str) -> bool:
		"""Ensure a specific model is available."""
		models = await self.list_models()
		model_names = [m.get('name', '') for m in models]
		
		# Check if exact model is available
		if model_name in model_names:
			print(f"✅ Model {model_name} already available")
			return True
		
		# Check if model without :latest tag is available
		if model_name.endswith(':latest'):
			base_name = model_name.replace(':latest', '')
			if base_name in model_names:
				print(f"✅ Model {base_name} available (equivalent to {model_name})")
				return True
		
		# Model not found, try to pull it
		print(f"📦 Model {model_name} not found, attempting to pull...")
		return self.pull_model(model_name)
	
	async def setup_complete_ollama(self, remove_old: bool = True) -> bool:
		"""Complete Ollama setup: install, start, pull models, cleanup."""
		print("🔧 Setting up Ollama for Browser-Use...")
		
		# 1. Check if Ollama is installed
		if not await self.check_ollama_installation():
			if not self.install_ollama():
				return False
			
			# Recheck after installation
			if not await self.check_ollama_installation():
				print("❌ Ollama installation verification failed")
				return False
		
		# 2. Check if service is running
		if not await self.check_service_running():
			if not self.start_ollama_service():
				return False
			
			# Wait and recheck
			await asyncio.sleep(5)
			if not await self.check_service_running():
				print("❌ Ollama service failed to start")
				return False
		
		# 3. Ensure required models are available
		for model in self.required_models:
			if not await self.ensure_model_available(model):
				print(f"❌ Failed to ensure model {model} is available")
				return False
		
		# 4. Remove old models if requested
		if remove_old:
			old_models = ["minicpm-v", "minicpm-v:latest", "openbmb/minicpm-v2.6"]
			print("🧹 Cleaning up old MiniCPM-V models...")
			self.remove_old_models(old_models)
		
		print("✅ Ollama setup complete!")
		return True
	
	async def health_check(self) -> Dict[str, Any]:
		"""Comprehensive health check."""
		health = {
			"ollama_installed": False,
			"service_running": False,
			"models_available": [],
			"required_models_ready": False,
			"overall_status": "failed"
		}
		
		# Check installation
		health["ollama_installed"] = await self.check_ollama_installation()
		if not health["ollama_installed"]:
			return health
		
		# Check service
		health["service_running"] = await self.check_service_running()
		if not health["service_running"]:
			return health
		
		# Check models
		models = await self.list_models()
		health["models_available"] = [m.get('name', '') for m in models]
		
		# Check required models
		required_available = all(
			any(req in available for available in health["models_available"]) 
			for req in self.required_models
		)
		health["required_models_ready"] = required_available
		
		if required_available:
			health["overall_status"] = "healthy"
		else:
			health["overall_status"] = "missing_models"
		
		return health


async def main():
	"""CLI interface for Ollama management."""
	import argparse
	
	parser = argparse.ArgumentParser(description="Ollama Manager for Browser-Use")
	parser.add_argument("--setup", action="store_true", help="Complete Ollama setup")
	parser.add_argument("--health", action="store_true", help="Health check")
	parser.add_argument("--model", default="moondream:latest", help="Model to use")
	
	args = parser.parse_args()
	
	manager = OllamaManager(model=args.model)
	
	if args.setup:
		success = await manager.setup_complete_ollama()
		if success:
			print("\n🎉 Ollama is ready for Browser-Use!")
		else:
			print("\n❌ Ollama setup failed")
			sys.exit(1)
	
	elif args.health:
		health = await manager.health_check()
		print(f"\n📊 Ollama Health Status:")
		for key, value in health.items():
			status = "✅" if value else "❌" if isinstance(value, bool) else "📋"
			print(f"{status} {key}: {value}")
		
		if health["overall_status"] != "healthy":
			print("\n💡 Run with --setup to fix issues")
			sys.exit(1)
	
	else:
		parser.print_help()


if __name__ == "__main__":
	asyncio.run(main())