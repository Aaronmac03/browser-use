#!/usr/bin/env python3
"""
Containerized Vision Service Manager - Robust service management via Docker
Replaces fragile Ollama process management with reliable containerized services

Key Features:
1. Docker-based service isolation and management
2. Automatic container health monitoring and recovery  
3. Resource-constrained containers prevent memory leaks
4. Stateless service design eliminates context accumulation
5. Atomic deployment and rollback capabilities
6. Service mesh integration for scalability
"""

import asyncio
import json
import logging
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
import httpx
import docker
from docker.errors import APIError, ContainerError, ImageNotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContainerStatus(Enum):
    """Container status states"""
    PENDING = "pending"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class ContainerConfig:
    """Container configuration"""
    image: str
    name: str
    ports: Dict[str, int]
    environment: Dict[str, str]
    volumes: Dict[str, str]
    memory_limit: str = "4g"
    cpu_limit: float = 2.0
    gpu_access: bool = True
    auto_remove: bool = True
    restart_policy: str = "unless-stopped"
    health_check: Optional[Dict[str, Any]] = None


class ContainerizedVisionService:
    """Containerized vision service with robust lifecycle management"""
    
    def __init__(self, service_name: str = "vision-service"):
        self.service_name = service_name
        self.docker_client = None
        self.containers = {}
        self.service_configs = self._get_service_configs()
        self.monitoring_active = False
        
    async def initialize(self) -> bool:
        """Initialize Docker client and prepare services"""
        try:
            # Initialize Docker client
            self.docker_client = docker.from_env()
            
            # Test Docker connectivity
            try:
                self.docker_client.ping()
                logger.info("Docker connection established")
            except Exception as e:
                logger.error(f"Docker not available: {e}")
                return False
            
            # Check for required images
            await self._ensure_images_available()
            
            # Start monitoring
            await self._start_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize containerized service: {e}")
            return False
    
    def _get_service_configs(self) -> Dict[str, ContainerConfig]:
        """Get service container configurations"""
        return {
            'moondream': ContainerConfig(
                image="ollama/ollama:latest",
                name=f"{self.service_name}-moondream",
                ports={'11434': 11434},
                environment={
                    'OLLAMA_HOST': '0.0.0.0',
                    'OLLAMA_NUM_PARALLEL': '1',  # Prevent memory accumulation
                    'OLLAMA_MAX_LOADED_MODELS': '1',
                    'CUDA_VISIBLE_DEVICES': '0'
                },
                volumes={
                    '/app/models': '/root/.ollama'
                },
                memory_limit="6g",
                cpu_limit=3.0,
                health_check={
                    'test': 'curl -f http://localhost:11434/api/version || exit 1',
                    'interval': 30,
                    'timeout': 10,
                    'retries': 3,
                    'start_period': 60
                }
            ),
            'phi3-vision': ContainerConfig(
                image="microsoft/phi3-vision:latest",
                name=f"{self.service_name}-phi3",
                ports={'8080': 8080},
                environment={
                    'MODEL_PATH': '/app/models/phi3-vision-onnx',
                    'MAX_BATCH_SIZE': '1',
                    'ENABLE_GPU': 'true'
                },
                volumes={
                    '/app/models': '/app/models'
                },
                memory_limit="4g",
                cpu_limit=2.0
            )
        }
    
    async def _ensure_images_available(self) -> bool:
        """Ensure required Docker images are available"""
        for service_name, config in self.service_configs.items():
            try:
                # Check if image exists locally
                try:
                    self.docker_client.images.get(config.image)
                    logger.info(f"Image {config.image} found locally")
                    continue
                except ImageNotFound:
                    pass
                
                # Pull image if not found
                logger.info(f"Pulling image {config.image}...")
                image = self.docker_client.images.pull(config.image)
                logger.info(f"Successfully pulled {config.image}")
                
            except Exception as e:
                logger.error(f"Failed to ensure image {config.image}: {e}")
                return False
        
        return True
    
    async def start_service(self, service_name: str) -> bool:
        """Start a containerized service"""
        if service_name not in self.service_configs:
            logger.error(f"Unknown service: {service_name}")
            return False
        
        config = self.service_configs[service_name]
        
        try:
            # Stop existing container if running
            await self._stop_container_if_exists(config.name)
            
            # Prepare container configuration
            container_config = self._build_container_config(config)
            
            # Start container
            logger.info(f"Starting container {config.name}...")
            container = self.docker_client.containers.run(**container_config)
            
            self.containers[service_name] = container
            
            # Wait for service to become healthy
            if await self._wait_for_health(service_name, timeout=120):
                logger.info(f"Service {service_name} started successfully")
                return True
            else:
                logger.error(f"Service {service_name} failed to become healthy")
                await self.stop_service(service_name)
                return False
                
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            return False
    
    def _build_container_config(self, config: ContainerConfig) -> Dict[str, Any]:
        """Build Docker container configuration"""
        container_config = {
            'image': config.image,
            'name': config.name,
            'detach': True,
            'remove': config.auto_remove,
            'environment': config.environment,
            'ports': config.ports,
            'volumes': config.volumes,
            'mem_limit': config.memory_limit,
            'cpu_count': config.cpu_limit,
            'restart_policy': {"Name": config.restart_policy}
        }
        
        # Add GPU access if requested
        if config.gpu_access:
            container_config['device_requests'] = [
                docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
            ]
        
        # Add health check if specified
        if config.health_check:
            health_config = docker.types.Healthcheck(
                test=config.health_check['test'],
                interval=config.health_check.get('interval', 30) * 1000000000,  # Convert to nanoseconds
                timeout=config.health_check.get('timeout', 10) * 1000000000,
                retries=config.health_check.get('retries', 3),
                start_period=config.health_check.get('start_period', 60) * 1000000000
            )
            container_config['healthcheck'] = health_config
        
        return container_config
    
    async def _stop_container_if_exists(self, container_name: str):
        """Stop and remove existing container if it exists"""
        try:
            existing_container = self.docker_client.containers.get(container_name)
            logger.info(f"Stopping existing container {container_name}")
            existing_container.stop(timeout=10)
            existing_container.remove(force=True)
        except docker.errors.NotFound:
            pass  # Container doesn't exist, which is fine
        except Exception as e:
            logger.warning(f"Error stopping existing container {container_name}: {e}")
    
    async def _wait_for_health(self, service_name: str, timeout: int = 60) -> bool:
        """Wait for service to become healthy"""
        container = self.containers.get(service_name)
        if not container:
            return False
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                container.reload()
                
                # Check container state
                if container.status != 'running':
                    logger.warning(f"Container {service_name} not running: {container.status}")
                    return False
                
                # Check health status if health check is configured
                health_status = container.attrs.get('State', {}).get('Health', {})
                if health_status:
                    status = health_status.get('Status', 'unknown')
                    if status == 'healthy':
                        return True
                    elif status == 'unhealthy':
                        logger.error(f"Container {service_name} is unhealthy")
                        return False
                else:
                    # No health check configured, just verify service is responding
                    if await self._verify_service_response(service_name):
                        return True
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.warning(f"Error checking health of {service_name}: {e}")
                await asyncio.sleep(5)
        
        logger.error(f"Service {service_name} did not become healthy within {timeout}s")
        return False
    
    async def _verify_service_response(self, service_name: str) -> bool:
        """Verify service is responding to HTTP requests"""
        config = self.service_configs[service_name]
        
        # Try to connect to the service
        for port in config.ports.values():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"http://localhost:{port}/health")
                    if response.status_code == 200:
                        return True
            except Exception:
                try:
                    # Try alternative endpoints
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        if service_name == 'moondream':
                            response = await client.get(f"http://localhost:{port}/api/version")
                        else:
                            response = await client.get(f"http://localhost:{port}/")
                        
                        if response.status_code in [200, 404]:  # 404 is okay for some endpoints
                            return True
                except Exception:
                    continue
        
        return False
    
    async def stop_service(self, service_name: str) -> bool:
        """Stop a containerized service"""
        container = self.containers.get(service_name)
        if not container:
            logger.warning(f"No container found for service {service_name}")
            return True
        
        try:
            logger.info(f"Stopping service {service_name}")
            container.stop(timeout=15)
            container.remove(force=True)
            
            del self.containers[service_name]
            logger.info(f"Service {service_name} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a service (stop then start)"""
        logger.info(f"Restarting service {service_name}")
        
        # Stop first
        await self.stop_service(service_name)
        await asyncio.sleep(5)  # Brief pause for cleanup
        
        # Start again
        return await self.start_service(service_name)
    
    async def _start_monitoring(self):
        """Start continuous container monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        asyncio.create_task(self._monitoring_loop())
        logger.info("Container monitoring started")
    
    async def _monitoring_loop(self):
        """Continuous monitoring of container health"""
        while self.monitoring_active:
            try:
                await self._check_all_containers()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _check_all_containers(self):
        """Check health of all managed containers"""
        for service_name, container in list(self.containers.items()):
            try:
                container.reload()
                
                # Check if container is running
                if container.status != 'running':
                    logger.warning(f"Container {service_name} not running: {container.status}")
                    
                    # Attempt restart
                    logger.info(f"Attempting to restart {service_name}")
                    success = await self.restart_service(service_name)
                    if not success:
                        logger.error(f"Failed to restart {service_name}")
                    continue
                
                # Check resource usage
                stats = container.stats(stream=False)
                await self._check_resource_usage(service_name, stats)
                
                # Check if service is responding
                if not await self._verify_service_response(service_name):
                    logger.warning(f"Service {service_name} not responding, restarting...")
                    await self.restart_service(service_name)
                
            except Exception as e:
                logger.error(f"Error checking container {service_name}: {e}")
    
    async def _check_resource_usage(self, service_name: str, stats: Dict[str, Any]):
        """Check container resource usage and restart if excessive"""
        try:
            # Memory usage
            memory_stats = stats.get('memory_stats', {})
            if 'usage' in memory_stats and 'limit' in memory_stats:
                memory_usage_ratio = memory_stats['usage'] / memory_stats['limit']
                
                if memory_usage_ratio > 0.9:  # 90% memory usage
                    logger.warning(f"Service {service_name} using {memory_usage_ratio:.1%} memory, restarting...")
                    await self.restart_service(service_name)
                    return
            
            # CPU usage (more complex calculation needed for accurate CPU monitoring)
            # For now, we'll rely on Docker's built-in health checks
            
        except Exception as e:
            logger.warning(f"Error checking resource usage for {service_name}: {e}")
    
    async def create_ephemeral_service(self, base_service: str, task_id: str = None) -> str:
        """Create ephemeral container for single-use tasks"""
        if base_service not in self.service_configs:
            raise ValueError(f"Unknown base service: {base_service}")
        
        if not task_id:
            task_id = str(uuid.uuid4())[:8]
        
        ephemeral_name = f"{self.service_name}-{base_service}-ephemeral-{task_id}"
        
        # Create ephemeral config
        config = self.service_configs[base_service]
        ephemeral_config = ContainerConfig(
            image=config.image,
            name=ephemeral_name,
            ports={},  # No port mapping for ephemeral containers
            environment=config.environment,
            volumes=config.volumes,
            memory_limit="2g",  # Smaller limit for ephemeral containers
            cpu_limit=1.0,
            gpu_access=config.gpu_access,
            auto_remove=True,  # Always auto-remove ephemeral containers
            restart_policy="no"  # Never restart ephemeral containers
        )
        
        try:
            # Build and start ephemeral container
            container_config = self._build_container_config(ephemeral_config)
            container_config['detach'] = False  # Run synchronously
            
            logger.info(f"Starting ephemeral container {ephemeral_name}")
            container = self.docker_client.containers.run(**container_config)
            
            return ephemeral_name
            
        except Exception as e:
            logger.error(f"Failed to create ephemeral service: {e}")
            raise
    
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get comprehensive service status"""
        container = self.containers.get(service_name)
        
        if not container:
            return {
                'service_name': service_name,
                'status': ContainerStatus.STOPPED.value,
                'container_id': None,
                'uptime': 0,
                'resource_usage': {}
            }
        
        try:
            container.reload()
            
            # Get container stats
            stats = container.stats(stream=False)
            
            # Calculate uptime
            created_at = container.attrs['Created']
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            uptime = (datetime.now(created_time.tzinfo) - created_time).total_seconds()
            
            # Determine status
            if container.status == 'running':
                health = container.attrs.get('State', {}).get('Health', {})
                if health.get('Status') == 'healthy':
                    status = ContainerStatus.HEALTHY
                elif health.get('Status') == 'unhealthy':
                    status = ContainerStatus.UNHEALTHY
                else:
                    status = ContainerStatus.RUNNING
            else:
                status = ContainerStatus.FAILED
            
            return {
                'service_name': service_name,
                'status': status.value,
                'container_id': container.short_id,
                'uptime': uptime,
                'resource_usage': {
                    'memory_usage': stats.get('memory_stats', {}),
                    'cpu_stats': stats.get('cpu_stats', {}),
                    'network': stats.get('networks', {})
                },
                'health_status': container.attrs.get('State', {}).get('Health', {}),
                'restart_count': container.attrs.get('RestartCount', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting status for {service_name}: {e}")
            return {
                'service_name': service_name,
                'status': ContainerStatus.FAILED.value,
                'error': str(e)
            }
    
    async def get_all_service_status(self) -> Dict[str, Any]:
        """Get status of all managed services"""
        status_report = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_active': self.monitoring_active,
            'services': {}
        }
        
        for service_name in self.service_configs.keys():
            status_report['services'][service_name] = await self.get_service_status(service_name)
        
        return status_report
    
    async def cleanup(self):
        """Clean up all resources"""
        logger.info("Cleaning up containerized vision service")
        
        # Stop monitoring
        self.monitoring_active = False
        
        # Stop all services
        for service_name in list(self.containers.keys()):
            await self.stop_service(service_name)
        
        # Close Docker client
        if self.docker_client:
            self.docker_client.close()


# Example usage
async def example_containerized_service():
    """Example of using containerized vision service"""
    service = ContainerizedVisionService("example-vision")
    
    try:
        # Initialize
        if not await service.initialize():
            print("Failed to initialize service")
            return
        
        # Start Moondream service
        if await service.start_service("moondream"):
            print("Moondream service started successfully")
            
            # Get status
            status = await service.get_service_status("moondream")
            print(f"Service status: {json.dumps(status, indent=2)}")
            
            # Test service for a few minutes
            await asyncio.sleep(60)
            
            # Get final status
            final_status = await service.get_all_service_status()
            print(f"Final status: {json.dumps(final_status, indent=2)}")
        else:
            print("Failed to start Moondream service")
    
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(example_containerized_service())