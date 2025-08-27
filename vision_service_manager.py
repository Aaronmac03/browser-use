#!/usr/bin/env python3
"""
Vision Service Manager - Handles reliable service management for vision models
Fixes Ollama service issues and provides robust service lifecycle management
"""

import asyncio
import json
import subprocess
import time
import psutil
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status states"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Service health information"""
    status: ServiceStatus
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    last_check: Optional[float] = None
    consecutive_failures: int = 0


class OllamaServiceManager:
    """Manages Ollama service lifecycle and health"""
    
    def __init__(self, endpoint: str = "http://localhost:11434"):
        self.endpoint = endpoint
        self.health = ServiceHealth(ServiceStatus.UNKNOWN)
        self.required_models = ["moondream:latest"]
        self.service_process = None
        self.health_check_interval = 30  # seconds
        self.max_startup_time = 120  # seconds
        self.max_consecutive_failures = 3
    
    async def check_installation(self) -> bool:
        """Check if Ollama is installed"""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Ollama installed: {result.stdout.strip()}")
                return True
            else:
                logger.warning(f"Ollama version check failed: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.warning(f"Ollama not found or not accessible: {e}")
            return False
    
    async def install_ollama(self) -> bool:
        """Install Ollama (Windows-specific)"""
        try:
            logger.info("Attempting to install Ollama...")
            
            # Download and install Ollama for Windows
            install_script = """
            $ErrorActionPreference = "Stop"
            Write-Host "Downloading Ollama installer..."
            $url = "https://ollama.com/download/windows"
            $output = "$env:TEMP\\OllamaSetup.exe"
            Invoke-WebRequest -Uri $url -OutFile $output
            Write-Host "Installing Ollama..."
            Start-Process -FilePath $output -ArgumentList "/S" -Wait
            Write-Host "Ollama installation completed"
            """
            
            result = subprocess.run(
                ["powershell", "-Command", install_script],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            if result.returncode == 0:
                logger.info("Ollama installation completed successfully")
                # Wait a moment for installation to complete
                await asyncio.sleep(5)
                return await self.check_installation()
            else:
                logger.error(f"Ollama installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install Ollama: {e}")
            return False
    
    async def is_service_running(self) -> bool:
        """Check if Ollama service is running"""
        try:
            # Check for Ollama processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        return True
                    if proc.info['cmdline'] and any('ollama' in cmd.lower() for cmd in proc.info['cmdline']):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            logger.warning(f"Error checking Ollama processes: {e}")
            return False
    
    async def start_service(self) -> bool:
        """Start Ollama service"""
        try:
            if await self.is_service_running():
                logger.info("Ollama service already running")
                return True
            
            logger.info("Starting Ollama service...")
            self.health.status = ServiceStatus.STARTING
            
            # Start Ollama service in background
            self.service_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
            )
            
            # Wait for service to start
            start_time = time.time()
            while time.time() - start_time < self.max_startup_time:
                if await self.health_check():
                    logger.info("Ollama service started successfully")
                    return True
                await asyncio.sleep(2)
            
            logger.error("Ollama service failed to start within timeout")
            await self.stop_service()
            return False
            
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")
            self.health.status = ServiceStatus.UNHEALTHY
            self.health.error_message = str(e)
            return False
    
    async def stop_service(self) -> bool:
        """Stop Ollama service"""
        try:
            logger.info("Stopping Ollama service...")
            self.health.status = ServiceStatus.STOPPING
            
            # Stop our managed process
            if self.service_process:
                try:
                    self.service_process.terminate()
                    self.service_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.service_process.kill()
                    self.service_process.wait()
                self.service_process = None
            
            # Kill any remaining Ollama processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        proc.terminate()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                    except:
                        pass
            
            logger.info("Ollama service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping Ollama service: {e}")
            return False
    
    async def restart_service(self) -> bool:
        """Restart Ollama service"""
        logger.info("Restarting Ollama service...")
        await self.stop_service()
        await asyncio.sleep(3)  # Wait for cleanup
        return await self.start_service()
    
    async def health_check(self) -> bool:
        """Perform health check on Ollama service"""
        start_time = time.time()
        
        try:
            timeout_config = httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=5.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.get(f"{self.endpoint}/api/version")
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    self.health.status = ServiceStatus.HEALTHY
                    self.health.response_time = response_time
                    self.health.error_message = None
                    self.health.last_check = time.time()
                    self.health.consecutive_failures = 0
                    return True
                else:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                    
        except Exception as e:
            response_time = time.time() - start_time
            self.health.status = ServiceStatus.UNHEALTHY
            self.health.response_time = response_time
            self.health.error_message = str(e)
            self.health.last_check = time.time()
            self.health.consecutive_failures += 1
            
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def ensure_models_available(self) -> bool:
        """Ensure required models are available"""
        try:
            # Get list of available models
            timeout_config = httpx.Timeout(connect=2.0, read=10.0, write=2.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                
                if response.status_code != 200:
                    logger.error(f"Failed to get model list: HTTP {response.status_code}")
                    return False
                
                data = response.json()
                available_models = [model.get('name', '') for model in data.get('models', [])]
                
                logger.info(f"Available models: {available_models}")
                
                # Check if required models are available
                missing_models = []
                for required_model in self.required_models:
                    if not any(required_model in model for model in available_models):
                        missing_models.append(required_model)
                
                if missing_models:
                    logger.info(f"Missing models: {missing_models}")
                    
                    # Attempt to pull missing models
                    for model in missing_models:
                        logger.info(f"Pulling model: {model}")
                        success = await self._pull_model(model)
                        if not success:
                            logger.error(f"Failed to pull model: {model}")
                            return False
                
                logger.info("All required models are available")
                return True
                
        except Exception as e:
            logger.error(f"Error checking models: {e}")
            return False
    
    async def _pull_model(self, model_name: str) -> bool:
        """Pull a model using Ollama API"""
        try:
            logger.info(f"Pulling model {model_name}...")
            
            timeout_config = httpx.Timeout(connect=5.0, read=300.0, write=5.0, pool=300.0)  # 5 minute timeout for model download
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(
                    f"{self.endpoint}/api/pull",
                    json={"name": model_name},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully pulled model: {model_name}")
                    return True
                else:
                    logger.error(f"Failed to pull model {model_name}: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False
    
    async def setup_complete_service(self) -> bool:
        """Complete setup of Ollama service with models"""
        logger.info("Starting complete Ollama service setup...")
        
        # Step 1: Check installation
        if not await self.check_installation():
            logger.info("Ollama not installed, attempting installation...")
            if not await self.install_ollama():
                logger.error("Failed to install Ollama")
                return False
        
        # Step 2: Start service
        if not await self.start_service():
            logger.error("Failed to start Ollama service")
            return False
        
        # Step 3: Ensure models are available
        if not await self.ensure_models_available():
            logger.error("Failed to ensure models are available")
            return False
        
        # Step 4: Final health check
        if not await self.health_check():
            logger.error("Final health check failed")
            return False
        
        logger.info("Ollama service setup completed successfully")
        return True
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get comprehensive service information"""
        info = {
            'installed': await self.check_installation(),
            'service_running': await self.is_service_running(),
            'health_status': self.health.status.value,
            'response_time': self.health.response_time,
            'error_message': self.health.error_message,
            'last_check': self.health.last_check,
            'consecutive_failures': self.health.consecutive_failures,
            'endpoint': self.endpoint
        }
        
        # Get model information if service is healthy
        if self.health.status == ServiceStatus.HEALTHY:
            try:
                timeout_config = httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=5.0)
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.get(f"{self.endpoint}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        info['available_models'] = [model.get('name', '') for model in data.get('models', [])]
                        info['required_models'] = self.required_models
                        info['models_ready'] = all(
                            any(req in avail for avail in info['available_models'])
                            for req in self.required_models
                        )
            except Exception as e:
                info['model_check_error'] = str(e)
        
        return info
    
    async def monitor_service(self, check_interval: int = 30):
        """Continuously monitor service health"""
        logger.info(f"Starting service monitoring (interval: {check_interval}s)")
        
        while True:
            try:
                is_healthy = await self.health_check()
                
                if not is_healthy and self.health.consecutive_failures >= self.max_consecutive_failures:
                    logger.warning(f"Service unhealthy for {self.health.consecutive_failures} consecutive checks, attempting restart")
                    await self.restart_service()
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                logger.info("Service monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in service monitoring: {e}")
                await asyncio.sleep(check_interval)


class VisionServiceManager:
    """High-level manager for all vision services"""
    
    def __init__(self):
        self.ollama_manager = OllamaServiceManager()
        self.services = {
            'ollama': self.ollama_manager
        }
    
    async def setup_all_services(self) -> Dict[str, bool]:
        """Setup all vision services"""
        results = {}
        
        logger.info("Setting up all vision services...")
        
        # Setup Ollama
        results['ollama'] = await self.ollama_manager.setup_complete_service()
        
        return results
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Health check all services"""
        results = {}
        
        # Check Ollama
        results['ollama'] = await self.ollama_manager.get_service_info()
        
        return results
    
    async def restart_all_services(self) -> Dict[str, bool]:
        """Restart all services"""
        results = {}
        
        # Restart Ollama
        results['ollama'] = await self.ollama_manager.restart_service()
        
        return results
    
    def get_overall_status(self) -> str:
        """Get overall status of all services"""
        if self.ollama_manager.health.status == ServiceStatus.HEALTHY:
            return "healthy"
        elif self.ollama_manager.health.status in [ServiceStatus.STARTING, ServiceStatus.STOPPING]:
            return "transitioning"
        else:
            return "unhealthy"


# CLI interface for service management
async def main():
    """CLI interface for vision service management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vision Service Manager")
    parser.add_argument("--setup", action="store_true", help="Setup all vision services")
    parser.add_argument("--health", action="store_true", help="Check health of all services")
    parser.add_argument("--restart", action="store_true", help="Restart all services")
    parser.add_argument("--monitor", action="store_true", help="Monitor services continuously")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    manager = VisionServiceManager()
    
    if args.setup:
        print("🚀 Setting up vision services...")
        results = await manager.setup_all_services()
        for service, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"{service}: {status}")
    
    elif args.health:
        print("🏥 Checking service health...")
        results = await manager.health_check_all()
        for service, info in results.items():
            print(f"\n{service.upper()} SERVICE:")
            for key, value in info.items():
                print(f"  {key}: {value}")
    
    elif args.restart:
        print("🔄 Restarting services...")
        results = await manager.restart_all_services()
        for service, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"{service}: {status}")
    
    elif args.monitor:
        print(f"👁️ Monitoring services (interval: {args.interval}s)...")
        try:
            await manager.ollama_manager.monitor_service(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())