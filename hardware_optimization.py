#!/usr/bin/env python3
"""
Hardware-specific optimization configurations for browser-use with local LLMs.
Optimized for different GPU/CPU combinations with privacy-first architecture.
"""

import logging
import os
import psutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class HardwareProfile:
    """Hardware profile for optimization."""
    name: str
    gpu_vram_gb: float
    cpu_cores: int
    ram_gb: float
    gpu_layers: int
    threads: int
    batch_size: int
    ubatch_size: int
    parallel_requests: int
    use_flash_attn: bool
    use_mlock: bool
    use_mmap: bool

class HardwareOptimizer:
    """Optimize llama.cpp configuration for specific hardware."""
    
    # Predefined hardware profiles
    PROFILES = {
        "gtx_1660_ti": HardwareProfile(
            name="GTX 1660 Ti + i7-9750H + 16GB RAM",
            gpu_vram_gb=6.0,
            cpu_cores=6,
            ram_gb=16.0,
            gpu_layers=35,      # Most layers on GPU for 7B Q4_K_M model
            threads=6,          # Match CPU cores
            batch_size=512,     # Balanced for 6GB VRAM
            ubatch_size=128,    # Efficient micro-batching
            parallel_requests=2, # Conservative for stability
            use_flash_attn=True, # Enable for performance
            use_mlock=True,     # Lock model in RAM
            use_mmap=False      # Disable for better GPU utilization
        ),
        
        "rtx_3060": HardwareProfile(
            name="RTX 3060 + Modern CPU + 16GB RAM",
            gpu_vram_gb=12.0,
            cpu_cores=8,
            ram_gb=16.0,
            gpu_layers=40,      # More layers for larger VRAM
            threads=8,
            batch_size=1024,    # Larger batches for 12GB VRAM
            ubatch_size=256,
            parallel_requests=3,
            use_flash_attn=True,
            use_mlock=True,
            use_mmap=False
        ),
        
        "cpu_only": HardwareProfile(
            name="CPU Only + 16GB+ RAM",
            gpu_vram_gb=0.0,
            cpu_cores=8,
            ram_gb=16.0,
            gpu_layers=0,       # No GPU acceleration
            threads=8,
            batch_size=256,     # Smaller batches for CPU
            ubatch_size=64,
            parallel_requests=1, # Single request for CPU
            use_flash_attn=False,
            use_mlock=True,
            use_mmap=True       # Use memory mapping for CPU
        ),
        
        "high_end": HardwareProfile(
            name="RTX 4080+ + High-end CPU + 32GB+ RAM",
            gpu_vram_gb=16.0,
            cpu_cores=12,
            ram_gb=32.0,
            gpu_layers=45,      # Maximum layers
            threads=12,
            batch_size=2048,    # Large batches
            ubatch_size=512,
            parallel_requests=4, # Multiple parallel requests
            use_flash_attn=True,
            use_mlock=True,
            use_mmap=False
        )
    }
    
    def __init__(self):
        self.detected_profile = None
        self.custom_profile = None
    
    def detect_hardware(self) -> HardwareProfile:
        """Auto-detect hardware and return optimal profile."""
        logger.info("[DETECT] Detecting hardware configuration...")
        
        # Get CPU info
        cpu_count = psutil.cpu_count(logical=False)  # Physical cores
        ram_gb = psutil.virtual_memory().total / (1024**3)
        
        logger.info(f"[CPU] Detected {cpu_count} CPU cores")
        logger.info(f"[RAM] Detected {ram_gb:.1f}GB RAM")
        
        # Try to detect GPU
        gpu_info = self._detect_gpu()
        
        if gpu_info:
            gpu_name, vram_gb = gpu_info
            logger.info(f"[GPU] Detected {gpu_name} with {vram_gb:.1f}GB VRAM")
            
            # Match to known profiles
            if "1660" in gpu_name.lower() and "ti" in gpu_name.lower():
                self.detected_profile = self.PROFILES["gtx_1660_ti"]
            elif "3060" in gpu_name.lower():
                self.detected_profile = self.PROFILES["rtx_3060"]
            elif any(x in gpu_name.lower() for x in ["4080", "4090", "3080", "3090"]):
                self.detected_profile = self.PROFILES["high_end"]
            else:
                # Create custom profile based on VRAM
                self.detected_profile = self._create_custom_gpu_profile(
                    gpu_name, vram_gb, cpu_count, ram_gb
                )
        else:
            logger.info("[GPU] No compatible GPU detected, using CPU-only profile")
            self.detected_profile = self.PROFILES["cpu_only"]
            self.detected_profile.cpu_cores = cpu_count
            self.detected_profile.ram_gb = ram_gb
            self.detected_profile.threads = min(cpu_count, 12)  # Cap at 12 threads
        
        logger.info(f"[PROFILE] Selected profile: {self.detected_profile.name}")
        return self.detected_profile
    
    def _detect_gpu(self) -> Optional[Tuple[str, float]]:
        """Detect GPU information using nvidia-smi or other methods."""
        try:
            # Try nvidia-smi first
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines and lines[0]:
                    parts = lines[0].split(', ')
                    if len(parts) >= 2:
                        gpu_name = parts[0].strip()
                        vram_mb = float(parts[1].strip())
                        vram_gb = vram_mb / 1024
                        return gpu_name, vram_gb
            
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"[GPU] nvidia-smi detection failed: {e}")
        
        # Try alternative detection methods here if needed
        return None
    
    def _create_custom_gpu_profile(
        self, 
        gpu_name: str, 
        vram_gb: float, 
        cpu_cores: int, 
        ram_gb: float
    ) -> HardwareProfile:
        """Create custom profile for unknown GPU."""
        
        # Estimate GPU layers based on VRAM (rough approximation for 7B Q4_K_M)
        if vram_gb >= 12:
            gpu_layers = 40
            batch_size = 1024
            parallel_requests = 3
        elif vram_gb >= 8:
            gpu_layers = 35
            batch_size = 512
            parallel_requests = 2
        elif vram_gb >= 6:
            gpu_layers = 30
            batch_size = 256
            parallel_requests = 2
        elif vram_gb >= 4:
            gpu_layers = 20
            batch_size = 128
            parallel_requests = 1
        else:
            gpu_layers = 10
            batch_size = 64
            parallel_requests = 1
        
        return HardwareProfile(
            name=f"Custom: {gpu_name}",
            gpu_vram_gb=vram_gb,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            gpu_layers=gpu_layers,
            threads=min(cpu_cores, 12),
            batch_size=batch_size,
            ubatch_size=batch_size // 4,
            parallel_requests=parallel_requests,
            use_flash_attn=vram_gb >= 6,
            use_mlock=ram_gb >= 16,
            use_mmap=vram_gb < 4
        )
    
    def generate_server_config(self, profile: HardwareProfile = None, model_name: str = None) -> str:
        """Generate optimized llama.cpp server configuration."""
        if profile is None:
            profile = self.detected_profile or self.detect_hardware()
        
        # Default model selection
        if model_name is None:
            model_name = "qwen2.5-14b-instruct-q4_k_m.gguf"
        
        # Support model shortcuts
        model_mapping = {
            "r1": "deepseek-r1-distill-llama-8b-q4_k_m.gguf",
            "qwen14b": "qwen2.5-14b-instruct-q4_k_m.gguf", 
            "qwen7b": "qwen2.5-7b-instruct-q4_k_m.gguf"
        }
        
        if model_name in model_mapping:
            model_name = model_mapping[model_name]
        
        config_lines = [
            f"REM {profile.name} Optimized Configuration",
            f"REM {profile.gpu_vram_gb:.1f}GB VRAM, {profile.cpu_cores} cores, {profile.ram_gb:.1f}GB RAM",
            f"REM Model: {model_name}",
            f"echo Optimizing for {profile.name}...",
            f"echo Model: {model_name}",
            "",
            "%SERVER_PATH% ^",
            f'    --model "e:\\ai\\llama-models\\{model_name}" ^',
            "    --host 0.0.0.0 ^",
            "    --port 8080 ^",
            "    --ctx-size 4096 ^",
            f"    --n-gpu-layers {profile.gpu_layers} ^",
            f"    --threads {profile.threads} ^",
            f"    --batch-size {profile.batch_size} ^",
            f"    --ubatch-size {profile.ubatch_size} ^",
            f"    --n-parallel {profile.parallel_requests} ^"
        ]
        
        # Add optional flags
        if profile.parallel_requests > 1:
            config_lines.append("    --cont-batching ^")
        
        if profile.use_flash_attn:
            config_lines.append("    --flash-attn ^")
        
        if profile.use_mlock:
            config_lines.append("    --mlock ^")
        
        if not profile.use_mmap:
            config_lines.append("    --no-mmap ^")
        
        # Remove the last ^ from the last line
        if config_lines[-1].endswith(" ^"):
            config_lines[-1] = config_lines[-1][:-2]
        
        return "\n".join(config_lines)
    
    def update_server_script(self, script_path: str = "e:/ai/start-llama-server.bat"):
        """Update the server script with optimized configuration."""
        script_path = Path(script_path)
        
        if not script_path.exists():
            logger.error(f"[ERROR] Server script not found: {script_path}")
            return False
        
        # Read current script
        content = script_path.read_text()
        
        # Find the server command section
        lines = content.split('\n')
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if "%SERVER_PATH%" in line and start_idx is None:
                start_idx = i
            elif start_idx is not None and not line.strip().endswith("^") and line.strip():
                end_idx = i + 1
                break
        
        if start_idx is None:
            logger.error("[ERROR] Could not find server command in script")
            return False
        
        if end_idx is None:
            end_idx = len(lines)
        
        # Generate new configuration
        profile = self.detect_hardware()
        new_config = self.generate_server_config(profile)
        
        # Replace the server command section
        new_lines = (
            lines[:start_idx] + 
            new_config.split('\n') + 
            lines[end_idx:]
        )
        
        # Write updated script
        script_path.write_text('\n'.join(new_lines))
        
        logger.info(f"[SUCCESS] Updated server script with {profile.name} optimization")
        return True
    
    def get_performance_recommendations(self) -> List[str]:
        """Get performance recommendations for current hardware."""
        profile = self.detected_profile or self.detect_hardware()
        
        recommendations = [
            f"Hardware Profile: {profile.name}",
            f"GPU Layers: {profile.gpu_layers} (utilizing {profile.gpu_vram_gb:.1f}GB VRAM)",
            f"CPU Threads: {profile.threads} (from {profile.cpu_cores} cores)",
            f"Batch Size: {profile.batch_size} (optimized for memory)",
            f"Parallel Requests: {profile.parallel_requests} (balanced for stability)"
        ]
        
        if profile.gpu_vram_gb >= 8:
            recommendations.append("✅ Excellent GPU memory for 7B models")
        elif profile.gpu_vram_gb >= 6:
            recommendations.append("✅ Good GPU memory for 7B models")
        elif profile.gpu_vram_gb >= 4:
            recommendations.append("⚠️  Limited GPU memory - consider smaller models")
        else:
            recommendations.append("❌ Insufficient GPU memory - CPU-only recommended")
        
        if profile.ram_gb >= 32:
            recommendations.append("✅ Excellent system RAM")
        elif profile.ram_gb >= 16:
            recommendations.append("✅ Good system RAM")
        else:
            recommendations.append("⚠️  Limited system RAM - monitor usage")
        
        return recommendations

# Usage example
async def optimize_hardware():
    """Optimize hardware configuration for current system."""
    optimizer = HardwareOptimizer()
    
    # Detect and optimize
    profile = optimizer.detect_hardware()
    
    # Update server script
    success = optimizer.update_server_script()
    
    if success:
        print("[SUCCESS] Hardware optimization complete!")
        print("\nRecommendations:")
        for rec in optimizer.get_performance_recommendations():
            print(f"  {rec}")
        
        print(f"\nOptimized for: {profile.name}")
        print(f"GPU Layers: {profile.gpu_layers}")
        print(f"Threads: {profile.threads}")
        print(f"Batch Size: {profile.batch_size}")
        
        return True
    else:
        print("[ERROR] Hardware optimization failed!")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(optimize_hardware())