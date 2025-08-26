#!/usr/bin/env python3
"""
Quick Ollama setup script for Browser-Use
Ensures Ollama is installed, running, and has the required models
"""

import asyncio
import sys
from ollama_manager import OllamaManager

async def main():
	"""Quick setup for Ollama with Browser-Use requirements."""
	print("🚀 Browser-Use Ollama Setup")
	print("=" * 40)
	
	# Initialize manager with required model
	manager = OllamaManager(model="moondream:latest")
	
	print("🔍 Checking current status...")
	health = await manager.health_check()
	
	if health["overall_status"] == "healthy":
		print("✅ Ollama is already set up correctly!")
		print("🎉 Ready to run Browser-Use hybrid agent")
		return
	
	print(f"⚠️  Current status: {health['overall_status']}")
	print("\n📋 Issues found:")
	if not health["ollama_installed"]:
		print("  ❌ Ollama not installed")
	if not health["service_running"]:
		print("  ❌ Ollama service not running")
	if not health["required_models_ready"]:
		print("  ❌ Required models missing")
	
	# Ask user if they want to proceed with setup
	response = input("\n🛠️  Proceed with automatic setup? [Y/n]: ").strip().lower()
	if response in ['n', 'no']:
		print("❌ Setup cancelled")
		return
	
	# Run complete setup
	print("\n🔧 Running complete Ollama setup...")
	success = await manager.setup_complete_ollama(remove_old=True)
	
	if success:
		print("\n✅ Setup complete!")
		print("🎉 Browser-Use is ready to run with vision capabilities")
		print("\n🚀 You can now run: python hybrid_agent.py")
	else:
		print("\n❌ Setup failed!")
		print("📋 Please check the error messages above and try manual installation:")
		print("   1. Install Ollama: https://ollama.ai")
		print("   2. Start service: ollama serve")
		print("   3. Pull model: ollama pull moondream")
		sys.exit(1)

if __name__ == "__main__":
	asyncio.run(main())