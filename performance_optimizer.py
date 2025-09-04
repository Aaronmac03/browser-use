#!/usr/bin/env python3
"""
Performance optimizer for browser-use with GTX 1660 Ti hardware.
Monitors and optimizes performance in real-time.
"""

import asyncio
import logging
import time
import psutil
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from hardware_optimization import HardwareOptimizer, HardwareProfile
from enhanced_local_llm import OptimizedLocalLLM, LocalLLMConfig

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring."""
    timestamp: float
    gpu_utilization: float
    gpu_memory_used: float
    gpu_memory_total: float
    cpu_utilization: float
    ram_used_gb: float
    ram_total_gb: float
    response_time: float
    tokens_per_second: float
    success_rate: float
    error_count: int

class PerformanceOptimizer:
    """Real-time performance optimizer for browser-use."""
    
    def __init__(self, config: LocalLLMConfig = None):
        self.config = config or LocalLLMConfig()
        self.hardware_optimizer = HardwareOptimizer()
        self.metrics_history: List[PerformanceMetrics] = []
        self.optimization_log: List[str] = []
        
        # Performance thresholds
        self.thresholds = {
            'max_response_time': 30.0,      # seconds
            'min_tokens_per_second': 5.0,   # tokens/sec
            'max_gpu_memory_usage': 0.9,    # 90% of VRAM
            'max_ram_usage': 0.8,           # 80% of RAM
            'min_success_rate': 0.8         # 80% success rate
        }
        
        # Optimization state
        self.current_profile: Optional[HardwareProfile] = None
        self.optimization_active = False
        self.last_optimization = 0
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start continuous performance monitoring."""
        logger.info("[MONITOR] Starting performance monitoring...")
        self.optimization_active = True
        
        while self.optimization_active:
            try:
                metrics = await self.collect_metrics()
                if metrics:
                    self.metrics_history.append(metrics)
                    
                    # Keep only last 100 metrics
                    if len(self.metrics_history) > 100:
                        self.metrics_history = self.metrics_history[-100:]
                    
                    # Check if optimization is needed
                    if await self.should_optimize(metrics):
                        await self.optimize_performance(metrics)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"[ERROR] Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        logger.info("[MONITOR] Stopping performance monitoring...")
        self.optimization_active = False
    
    async def collect_metrics(self) -> Optional[PerformanceMetrics]:
        """Collect current performance metrics."""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            ram_used_gb = memory.used / (1024**3)
            ram_total_gb = memory.total / (1024**3)
            
            # GPU metrics (if available)
            gpu_util, gpu_mem_used, gpu_mem_total = await self._get_gpu_metrics()
            
            # LLM performance metrics
            response_time, tokens_per_second, success_rate, error_count = await self._get_llm_metrics()
            
            return PerformanceMetrics(
                timestamp=time.time(),
                gpu_utilization=gpu_util,
                gpu_memory_used=gpu_mem_used,
                gpu_memory_total=gpu_mem_total,
                cpu_utilization=cpu_percent,
                ram_used_gb=ram_used_gb,
                ram_total_gb=ram_total_gb,
                response_time=response_time,
                tokens_per_second=tokens_per_second,
                success_rate=success_rate,
                error_count=error_count
            )
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to collect metrics: {e}")
            return None
    
    async def _get_gpu_metrics(self) -> tuple:
        """Get GPU utilization and memory metrics."""
        try:
            import subprocess
            result = subprocess.run([
                "nvidia-smi", 
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines and lines[0]:
                    parts = lines[0].split(', ')
                    if len(parts) >= 3:
                        gpu_util = float(parts[0])
                        gpu_mem_used = float(parts[1])
                        gpu_mem_total = float(parts[2])
                        return gpu_util, gpu_mem_used, gpu_mem_total
        
        except Exception as e:
            logger.debug(f"[GPU] GPU metrics unavailable: {e}")
        
        return 0.0, 0.0, 0.0
    
    async def _get_llm_metrics(self) -> tuple:
        """Get LLM performance metrics."""
        # This would integrate with the actual LLM client
        # For now, return placeholder values
        response_time = 10.0  # Average response time
        tokens_per_second = 15.0  # Tokens per second
        success_rate = 0.85  # Success rate
        error_count = 2  # Error count
        
        return response_time, tokens_per_second, success_rate, error_count
    
    async def should_optimize(self, metrics: PerformanceMetrics) -> bool:
        """Determine if performance optimization is needed."""
        # Don't optimize too frequently
        if time.time() - self.last_optimization < 300:  # 5 minutes
            return False
        
        # Check performance thresholds
        issues = []
        
        if metrics.response_time > self.thresholds['max_response_time']:
            issues.append(f"Slow response time: {metrics.response_time:.1f}s")
        
        if metrics.tokens_per_second < self.thresholds['min_tokens_per_second']:
            issues.append(f"Low token rate: {metrics.tokens_per_second:.1f} tokens/s")
        
        if metrics.gpu_memory_total > 0:
            gpu_usage = metrics.gpu_memory_used / metrics.gpu_memory_total
            if gpu_usage > self.thresholds['max_gpu_memory_usage']:
                issues.append(f"High GPU memory usage: {gpu_usage:.1%}")
        
        ram_usage = metrics.ram_used_gb / metrics.ram_total_gb
        if ram_usage > self.thresholds['max_ram_usage']:
            issues.append(f"High RAM usage: {ram_usage:.1%}")
        
        if metrics.success_rate < self.thresholds['min_success_rate']:
            issues.append(f"Low success rate: {metrics.success_rate:.1%}")
        
        if issues:
            logger.warning(f"[OPTIMIZE] Performance issues detected: {', '.join(issues)}")
            return True
        
        return False
    
    async def optimize_performance(self, metrics: PerformanceMetrics):
        """Optimize performance based on current metrics."""
        logger.info("[OPTIMIZE] Starting performance optimization...")
        self.last_optimization = time.time()
        
        optimizations = []
        
        # GPU memory optimization
        if metrics.gpu_memory_total > 0:
            gpu_usage = metrics.gpu_memory_used / metrics.gpu_memory_total
            if gpu_usage > 0.9:
                optimizations.append("Reduce GPU layers")
                await self._optimize_gpu_layers(-5)
            elif gpu_usage < 0.5 and metrics.response_time > 15:
                optimizations.append("Increase GPU layers")
                await self._optimize_gpu_layers(5)
        
        # Response time optimization
        if metrics.response_time > 20:
            optimizations.append("Reduce batch size")
            await self._optimize_batch_size(0.8)
        elif metrics.response_time < 5 and metrics.tokens_per_second > 20:
            optimizations.append("Increase batch size")
            await self._optimize_batch_size(1.2)
        
        # Memory optimization
        ram_usage = metrics.ram_used_gb / metrics.ram_total_gb
        if ram_usage > 0.8:
            optimizations.append("Enable memory optimization")
            await self._optimize_memory_usage()
        
        # Log optimizations
        if optimizations:
            opt_msg = f"Applied optimizations: {', '.join(optimizations)}"
            self.optimization_log.append(f"{time.time()}: {opt_msg}")
            logger.info(f"[OPTIMIZE] {opt_msg}")
        else:
            logger.info("[OPTIMIZE] No optimizations needed")
    
    async def _optimize_gpu_layers(self, delta: int):
        """Adjust GPU layers for optimization."""
        try:
            profile = self.hardware_optimizer.detected_profile
            if profile:
                new_layers = max(0, min(45, profile.gpu_layers + delta))
                profile.gpu_layers = new_layers
                
                # Update server configuration
                self.hardware_optimizer.update_server_script()
                logger.info(f"[GPU] Adjusted GPU layers to {new_layers}")
        
        except Exception as e:
            logger.error(f"[ERROR] GPU layer optimization failed: {e}")
    
    async def _optimize_batch_size(self, multiplier: float):
        """Adjust batch size for optimization."""
        try:
            profile = self.hardware_optimizer.detected_profile
            if profile:
                new_batch_size = int(profile.batch_size * multiplier)
                new_batch_size = max(64, min(2048, new_batch_size))
                profile.batch_size = new_batch_size
                profile.ubatch_size = new_batch_size // 4
                
                # Update server configuration
                self.hardware_optimizer.update_server_script()
                logger.info(f"[BATCH] Adjusted batch size to {new_batch_size}")
        
        except Exception as e:
            logger.error(f"[ERROR] Batch size optimization failed: {e}")
    
    async def _optimize_memory_usage(self):
        """Optimize memory usage."""
        try:
            # Enable memory optimizations
            profile = self.hardware_optimizer.detected_profile
            if profile:
                profile.use_mlock = True
                profile.use_mmap = False
                
                # Update server configuration
                self.hardware_optimizer.update_server_script()
                logger.info("[MEMORY] Enabled memory optimizations")
        
        except Exception as e:
            logger.error(f"[ERROR] Memory optimization failed: {e}")
    
    def get_performance_report(self) -> Dict:
        """Generate performance report."""
        if not self.metrics_history:
            return {"error": "No metrics available"}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 measurements
        
        avg_response_time = sum(m.response_time for m in recent_metrics) / len(recent_metrics)
        avg_tokens_per_sec = sum(m.tokens_per_second for m in recent_metrics) / len(recent_metrics)
        avg_success_rate = sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
        
        latest = recent_metrics[-1]
        
        return {
            "timestamp": latest.timestamp,
            "performance": {
                "avg_response_time": avg_response_time,
                "avg_tokens_per_second": avg_tokens_per_sec,
                "avg_success_rate": avg_success_rate,
                "current_gpu_usage": f"{latest.gpu_memory_used:.0f}MB / {latest.gpu_memory_total:.0f}MB",
                "current_ram_usage": f"{latest.ram_used_gb:.1f}GB / {latest.ram_total_gb:.1f}GB"
            },
            "optimizations_applied": len(self.optimization_log),
            "recent_optimizations": self.optimization_log[-5:],
            "status": self._get_performance_status(latest)
        }
    
    def _get_performance_status(self, metrics: PerformanceMetrics) -> str:
        """Get current performance status."""
        if metrics.response_time <= 10 and metrics.tokens_per_second >= 15 and metrics.success_rate >= 0.9:
            return "Excellent"
        elif metrics.response_time <= 20 and metrics.tokens_per_second >= 10 and metrics.success_rate >= 0.8:
            return "Good"
        elif metrics.response_time <= 30 and metrics.tokens_per_second >= 5 and metrics.success_rate >= 0.7:
            return "Fair"
        else:
            return "Poor"
    
    async def save_performance_data(self, filepath: str = "e:/ai/browser-use/performance_data.json"):
        """Save performance data to file."""
        try:
            data = {
                "metrics_history": [asdict(m) for m in self.metrics_history[-50:]],  # Last 50 metrics
                "optimization_log": self.optimization_log,
                "performance_report": self.get_performance_report(),
                "hardware_profile": asdict(self.hardware_optimizer.detected_profile) if self.hardware_optimizer.detected_profile else None
            }
            
            Path(filepath).write_text(json.dumps(data, indent=2))
            logger.info(f"[SAVE] Performance data saved to {filepath}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to save performance data: {e}")

# Usage example
async def main():
    """Run performance optimization."""
    logging.basicConfig(level=logging.INFO)
    
    optimizer = PerformanceOptimizer()
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(optimizer.start_monitoring(interval=60))
    
    try:
        # Run for 10 minutes as example
        await asyncio.sleep(600)
        
    finally:
        optimizer.stop_monitoring()
        await monitor_task
        
        # Generate final report
        report = optimizer.get_performance_report()
        print("\n" + "="*50)
        print("PERFORMANCE OPTIMIZATION REPORT")
        print("="*50)
        print(json.dumps(report, indent=2))
        
        # Save data
        await optimizer.save_performance_data()

if __name__ == "__main__":
    asyncio.run(main())