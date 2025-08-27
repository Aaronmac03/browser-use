#!/usr/bin/env python3
"""
llama.cpp Server Management for Browser-Use
Replaces Ollama with llama.cpp server for Moondream2 GGUF vision models
"""

import asyncio
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from pydantic import BaseModel


class LlamaCppServerStatus(BaseModel):
	"""Status of llama.cpp server"""
	running: bool = False
	endpoint: str = "http://localhost:8080"
	model_loaded: bool = False
	model_name: str = ""
	version: str = ""


class LlamaCppManager:
	"""Manager for llama.cpp server with Moondream2 GGUF models."""
	
	def __init__(self, endpoint: str = "http://localhost:8080", model_path: Optional[str] = None):
		"""Initialize llama.cpp server manager.
		
		Args:
			endpoint: llama.cpp server endpoint (default: http://localhost:8080)
			model_path: Path to Moondream2 GGUF model file
		"""
		self.endpoint = endpoint
		self.model_path = model_path or self._find_moondream_model()
		self.server_process = None
		
	def _find_moondream_model(self) -> Optional[str]:
		"""Try to find Moondream2 GGUF model in common locations."""
		possible_locations = [
			"./models/moondream2.gguf",
			"./models/moondream2-q4_k_m.gguf",
			"./models/moondream2-f16.gguf",
			os.path.expanduser("~/models/moondream2.gguf"),
			os.path.expanduser("~/models/moondream2-q4_k_m.gguf"),
			"/models/moondream2.gguf",  # Docker/container path
		]
		
		for path in possible_locations:
			if os.path.exists(path):
				print(f"[LlamaCppManager] Found Moondream2 model: {path}")
				return path
		
		print("[LlamaCppManager] No Moondream2 GGUF model found. Please specify model_path.")
		return None
	
	async def check_server_status(self) -> LlamaCppServerStatus:
		"""Check if llama.cpp server is running and healthy."""
		status = LlamaCppServerStatus(endpoint=self.endpoint)
		
		try:
			timeout_config = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				# Check health endpoint
				health_response = await client.get(f"{self.endpoint}/health")
				if health_response.status_code == 200:
					status.running = True
					
					# Try to get model info
					try:
						props_response = await client.get(f"{self.endpoint}/props")
						if props_response.status_code == 200:
							props = props_response.json()
							status.model_loaded = True
							status.model_name = props.get("default_generation_settings", {}).get("model", "unknown")
					except:
						pass  # Model info not critical
		
		except Exception as e:
			print(f"[LlamaCppManager] Server check failed: {e}")
			status.running = False
		
		return status
	
	def start_server(self, additional_args: Optional[list] = None) -> bool:
		"""Start llama.cpp server with Moondream2 model.
		
		Args:
			additional_args: Additional command line arguments for llama.cpp server
			
		Returns:
			bool: True if server started successfully
		"""
		if not self.model_path:
			print("[LlamaCppManager] ERROR: No model path specified. Cannot start server.")
			return False
		
		if not os.path.exists(self.model_path):
			print(f"[LlamaCppManager] ERROR: Model file not found: {self.model_path}")
			return False
		
		# Find llama.cpp server executable
		server_executable = self._find_server_executable()
		if not server_executable:
			print("[LlamaCppManager] ERROR: llama.cpp server executable not found.")
			return False
		
		# Build command
		cmd = [
			server_executable,
			"-m", self.model_path,
			"--host", "0.0.0.0",
			"--port", "8080",
			"--ctx-size", "2048",
			"--threads", str(os.cpu_count() or 4),
			"--mlock",  # Keep model in memory
			"--log-format", "json",
			"--verbose"
		]
		
		if additional_args:
			cmd.extend(additional_args)
		
		try:
			print(f"[LlamaCppManager] Starting server: {' '.join(cmd)}")
			self.server_process = subprocess.Popen(
				cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True
			)
			
			# Wait a moment for server to start
			time.sleep(3)
			
			# Check if process is still running
			if self.server_process.poll() is None:
				print("[LlamaCppManager] Server started successfully")
				return True
			else:
				stdout, stderr = self.server_process.communicate()
				print(f"[LlamaCppManager] Server failed to start. STDOUT: {stdout}")
				print(f"[LlamaCppManager] Server failed to start. STDERR: {stderr}")
				return False
		
		except Exception as e:
			print(f"[LlamaCppManager] Failed to start server: {e}")
			return False
	
	def _find_server_executable(self) -> Optional[str]:
		"""Find llama.cpp server executable."""
		possible_names = [
			"llama-server",
			"llama-cpp-server", 
			"server",
			"llama.cpp-server"
		]
		
		# Check in PATH first
		for name in possible_names:
			try:
				result = subprocess.run(["which", name], capture_output=True, text=True)
				if result.returncode == 0:
					return name
			except:
				pass
		
		# Check common installation paths
		possible_paths = [
			"./llama-server",
			"./server",
			"/usr/local/bin/llama-server",
			"/usr/bin/llama-server",
			os.path.expanduser("~/llama.cpp/llama-server"),
			os.path.expanduser("~/llama.cpp/server"),
		]
		
		for path in possible_paths:
			if os.path.exists(path) and os.access(path, os.X_OK):
				return path
		
		return None
	
	def stop_server(self) -> bool:
		"""Stop the llama.cpp server."""
		if self.server_process:
			try:
				self.server_process.terminate()
				self.server_process.wait(timeout=10)
				print("[LlamaCppManager] Server stopped")
				return True
			except subprocess.TimeoutExpired:
				self.server_process.kill()
				self.server_process.wait()
				print("[LlamaCppManager] Server force-killed")
				return True
			except Exception as e:
				print(f"[LlamaCppManager] Error stopping server: {e}")
				return False
		
		return True
	
	async def ensure_server_running(self) -> bool:
		"""Ensure llama.cpp server is running and healthy."""
		status = await self.check_server_status()
		
		if status.running and status.model_loaded:
			print("[LlamaCppManager] Server is already running and healthy")
			return True
		
		print("[LlamaCppManager] Server not running, attempting to start...")
		if self.start_server():
			# Wait for server to be ready
			for i in range(10):  # Wait up to 30 seconds
				await asyncio.sleep(3)
				status = await self.check_server_status()
				if status.running:
					print(f"[LlamaCppManager] Server ready after {(i+1)*3} seconds")
					return True
			
			print("[LlamaCppManager] Server started but not responding properly")
			return False
		
		return False
	
	async def test_vision_capability(self, test_image_path: Optional[str] = None) -> Dict[str, Any]:
		"""Test the vision capability of the loaded model."""
		if not await self.ensure_server_running():
			return {"success": False, "error": "Server not running"}
		
		# Create a simple test image if none provided
		if not test_image_path:
			test_image_path = self._create_test_image()
		
		if not test_image_path or not os.path.exists(test_image_path):
			return {"success": False, "error": "No test image available"}
		
		# Convert image to base64
		import base64
		try:
			with open(test_image_path, "rb") as f:
				image_data = base64.b64encode(f.read()).decode()
		except Exception as e:
			return {"success": False, "error": f"Failed to read image: {e}"}
		
		# Test vision request
		try:
			timeout_config = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
			async with httpx.AsyncClient(timeout=timeout_config) as client:
				payload = {
					"messages": [{
						"role": "user",
						"content": [
							{"type": "text", "text": "Describe what you see in this image."},
							{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
						]
					}],
					"max_tokens": 200,
					"temperature": 0.1
				}
				
				response = await client.post(f"{self.endpoint}/v1/chat/completions", json=payload)
				response.raise_for_status()
				
				result = response.json()
				if "choices" in result and result["choices"]:
					description = result["choices"][0]["message"]["content"]
					return {
						"success": True,
						"description": description,
						"response_time": response.elapsed.total_seconds()
					}
				else:
					return {"success": False, "error": "No response from model"}
		
		except Exception as e:
			return {"success": False, "error": f"Vision test failed: {e}"}
	
	def _create_test_image(self) -> Optional[str]:
		"""Create a simple test image for vision testing."""
		try:
			from PIL import Image, ImageDraw, ImageFont
			
			# Create a simple test image
			img = Image.new('RGB', (300, 200), color='white')
			draw = ImageDraw.Draw(img)
			
			# Draw some simple shapes and text
			draw.rectangle([50, 50, 150, 100], fill='blue', outline='black')
			draw.ellipse([180, 80, 250, 130], fill='red', outline='black')
			draw.text((60, 150), "Test Image", fill='black')
			
			test_path = "test_vision.jpg"
			img.save(test_path, "JPEG")
			return test_path
			
		except ImportError:
			print("[LlamaCppManager] PIL not available, cannot create test image")
			return None
		except Exception as e:
			print(f"[LlamaCppManager] Failed to create test image: {e}")
			return None


async def main():
	"""Command line interface for llama.cpp server management."""
	import argparse
	
	parser = argparse.ArgumentParser(description="Manage llama.cpp server for Browser-Use")
	parser.add_argument("--model-path", help="Path to Moondream2 GGUF model file")
	parser.add_argument("--endpoint", default="http://localhost:8080", help="Server endpoint")
	parser.add_argument("--start", action="store_true", help="Start the server")
	parser.add_argument("--stop", action="store_true", help="Stop the server")
	parser.add_argument("--status", action="store_true", help="Check server status")
	parser.add_argument("--test", action="store_true", help="Test vision capability")
	
	args = parser.parse_args()
	
	manager = LlamaCppManager(endpoint=args.endpoint, model_path=args.model_path)
	
	if args.start:
		success = manager.start_server()
		sys.exit(0 if success else 1)
	
	elif args.stop:
		success = manager.stop_server()
		sys.exit(0 if success else 1)
	
	elif args.status:
		status = await manager.check_server_status()
		print(json.dumps(status.model_dump(), indent=2))
		sys.exit(0 if status.running else 1)
	
	elif args.test:
		result = await manager.test_vision_capability()
		print(json.dumps(result, indent=2))
		sys.exit(0 if result.get("success", False) else 1)
	
	else:
		# Default: show status
		status = await manager.check_server_status()
		print(json.dumps(status.model_dump(), indent=2))


if __name__ == "__main__":
	asyncio.run(main())