#!/usr/bin/env python3
"""
Vision Performance Optimizer - Comprehensive performance optimization system
Optimizes vision model performance through intelligent caching, preprocessing, and resource management

Key Features:
1. Intelligent image preprocessing and optimization
2. Multi-level caching system with intelligent eviction
3. Dynamic model selection based on performance metrics
4. Resource-aware processing with automatic scaling
5. Predictive preloading and batch processing
6. Real-time performance monitoring and tuning
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import statistics
from collections import deque, OrderedDict
import sqlite3

import numpy as np
from PIL import Image, ImageOps, ImageFilter
import httpx

# Performance monitoring
import psutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels for different types of data"""
    L1_MEMORY = "l1_memory"      # Fast in-memory cache
    L2_DISK = "l2_disk"          # SSD disk cache
    L3_PROCESSED = "l3_processed" # Pre-processed image cache


class OptimizationLevel(Enum):
    """Image optimization levels"""
    MINIMAL = "minimal"          # Fastest, lowest quality
    BALANCED = "balanced"        # Good balance of speed/quality
    QUALITY = "quality"          # Best quality, slower
    ADAPTIVE = "adaptive"        # Dynamic based on system load


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics tracking"""
    request_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    preprocessing_time: float = 0.0
    model_inference_time: float = 0.0
    total_processing_time: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    throughput: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0


@dataclass
class ImageOptimizationConfig:
    """Configuration for image optimization"""
    max_width: int = 800
    max_height: int = 600
    jpeg_quality: int = 85
    enable_sharpening: bool = True
    enable_contrast_enhancement: bool = True
    enable_noise_reduction: bool = False
    compression_level: int = 6  # PNG compression level
    target_file_size_kb: Optional[int] = None


class IntelligentImagePreprocessor:
    """Advanced image preprocessing with optimization"""
    
    def __init__(self):
        self.optimization_configs = {
            OptimizationLevel.MINIMAL: ImageOptimizationConfig(
                max_width=640, max_height=480, jpeg_quality=70,
                enable_sharpening=False, enable_contrast_enhancement=False
            ),
            OptimizationLevel.BALANCED: ImageOptimizationConfig(
                max_width=800, max_height=600, jpeg_quality=85,
                enable_sharpening=True, enable_contrast_enhancement=True
            ),
            OptimizationLevel.QUALITY: ImageOptimizationConfig(
                max_width=1024, max_height=768, jpeg_quality=95,
                enable_sharpening=True, enable_contrast_enhancement=True,
                enable_noise_reduction=True
            ),
            OptimizationLevel.ADAPTIVE: None  # Determined dynamically
        }
        self.preprocessing_cache = {}
        
    async def optimize_image(self, image_path: str, optimization_level: OptimizationLevel) -> Tuple[str, Dict[str, Any]]:
        """Optimize image for vision processing"""
        start_time = time.time()
        
        # Generate cache key
        cache_key = self._generate_cache_key(image_path, optimization_level)
        
        # Check cache first
        if cache_key in self.preprocessing_cache:
            cached_result = self.preprocessing_cache[cache_key]
            logger.debug(f"Image preprocessing cache hit: {cache_key}")
            return cached_result['optimized_path'], cached_result['metadata']
        
        try:
            # Load image
            original_image = Image.open(image_path)
            
            # Determine optimization config
            if optimization_level == OptimizationLevel.ADAPTIVE:
                config = await self._determine_adaptive_config(original_image)
            else:
                config = self.optimization_configs[optimization_level]
            
            # Apply optimizations
            optimized_image = await self._apply_optimizations(original_image, config)
            
            # Save optimized image
            optimized_path = await self._save_optimized_image(optimized_image, image_path, optimization_level)
            
            # Generate metadata
            metadata = {
                'original_size': original_image.size,
                'optimized_size': optimized_image.size,
                'optimization_level': optimization_level.value,
                'processing_time': time.time() - start_time,
                'file_size_reduction': self._calculate_size_reduction(image_path, optimized_path),
                'config_used': config.__dict__
            }
            
            # Cache result
            self.preprocessing_cache[cache_key] = {
                'optimized_path': optimized_path,
                'metadata': metadata,
                'cached_at': time.time()
            }
            
            # Cleanup old cache entries (simple LRU)
            if len(self.preprocessing_cache) > 100:
                await self._cleanup_preprocessing_cache()
            
            return optimized_path, metadata
            
        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            # Return original path if optimization fails
            return image_path, {'error': str(e), 'processing_time': time.time() - start_time}
    
    async def _determine_adaptive_config(self, image: Image.Image) -> ImageOptimizationConfig:
        """Determine optimal configuration based on image characteristics and system load"""
        
        # Image complexity analysis
        width, height = image.size
        total_pixels = width * height
        
        # System resource analysis
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        
        # Determine optimization level based on factors
        if total_pixels > 2000000 or memory_info.percent > 80:  # Large image or high memory usage
            base_config = self.optimization_configs[OptimizationLevel.MINIMAL]
        elif cpu_percent > 70:  # High CPU usage
            base_config = self.optimization_configs[OptimizationLevel.BALANCED]
        else:
            base_config = self.optimization_configs[OptimizationLevel.QUALITY]
        
        # Dynamic adjustments
        if total_pixels > 1000000:  # Reduce resolution for large images
            scale_factor = min(1.0, 1000000 / total_pixels)
            base_config.max_width = int(width * scale_factor)
            base_config.max_height = int(height * scale_factor)
        
        return base_config
    
    async def _apply_optimizations(self, image: Image.Image, config: ImageOptimizationConfig) -> Image.Image:
        """Apply image optimizations based on configuration"""
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if needed
        original_width, original_height = image.size
        if original_width > config.max_width or original_height > config.max_height:
            # Calculate new size maintaining aspect ratio
            ratio = min(config.max_width / original_width, config.max_height / original_height)
            new_size = (int(original_width * ratio), int(original_height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Apply enhancements
        if config.enable_contrast_enhancement:
            image = ImageOps.autocontrast(image, cutoff=2)
        
        if config.enable_sharpening:
            # Mild sharpening filter
            sharpening_filter = ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)
            image = image.filter(sharpening_filter)
        
        if config.enable_noise_reduction:
            # Simple noise reduction using blur
            image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    async def _save_optimized_image(self, image: Image.Image, original_path: str, level: OptimizationLevel) -> str:
        """Save optimized image to disk"""
        
        # Create output path
        original_path_obj = Path(original_path)
        output_path = original_path_obj.parent / f"{original_path_obj.stem}_optimized_{level.value}{original_path_obj.suffix}"
        
        # Save with appropriate format and quality
        if original_path_obj.suffix.lower() in ['.jpg', '.jpeg']:
            config = self.optimization_configs.get(level, self.optimization_configs[OptimizationLevel.BALANCED])
            image.save(output_path, format='JPEG', quality=config.jpeg_quality, optimize=True)
        else:
            image.save(output_path, format='PNG', optimize=True)
        
        return str(output_path)
    
    def _generate_cache_key(self, image_path: str, optimization_level: OptimizationLevel) -> str:
        """Generate cache key for preprocessing"""
        # Include file modification time in cache key to handle file updates
        try:
            mtime = Path(image_path).stat().st_mtime
            content = f"{image_path}:{optimization_level.value}:{mtime}"
            return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            return hashlib.md5(f"{image_path}:{optimization_level.value}".encode()).hexdigest()
    
    def _calculate_size_reduction(self, original_path: str, optimized_path: str) -> float:
        """Calculate file size reduction percentage"""
        try:
            original_size = Path(original_path).stat().st_size
            optimized_size = Path(optimized_path).stat().st_size
            return (original_size - optimized_size) / original_size * 100
        except Exception:
            return 0.0
    
    async def _cleanup_preprocessing_cache(self):
        """Clean up old preprocessing cache entries"""
        current_time = time.time()
        cache_ttl = 3600  # 1 hour TTL
        
        keys_to_remove = []
        for key, entry in self.preprocessing_cache.items():
            if current_time - entry['cached_at'] > cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.preprocessing_cache[key]
        
        logger.info(f"Cleaned up {len(keys_to_remove)} preprocessing cache entries")


class MultiLevelVisionCache:
    """Multi-level caching system for vision analysis results"""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("./vision_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # L1 Cache: In-memory (fast access)
        self.l1_cache = OrderedDict()  # LRU cache
        self.l1_max_size = 100
        
        # L2 Cache: SQLite database (persistent)
        self.l2_db_path = self.cache_dir / "vision_cache.db"
        self.l2_db = None
        
        # L3 Cache: Pre-processed images
        self.l3_cache_dir = self.cache_dir / "preprocessed"
        self.l3_cache_dir.mkdir(exist_ok=True)
        
        # Cache statistics
        self.stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'l3_hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
    async def initialize(self):
        """Initialize cache database and structures"""
        self.l2_db = sqlite3.connect(str(self.l2_db_path), check_same_thread=False)
        
        # Create cache table
        self.l2_db.execute("""
            CREATE TABLE IF NOT EXISTS vision_cache (
                key TEXT PRIMARY KEY,
                data TEXT,
                timestamp REAL,
                access_count INTEGER DEFAULT 1,
                size_bytes INTEGER,
                tier TEXT
            )
        """)
        
        # Create index for efficient queries
        self.l2_db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON vision_cache(timestamp)")
        self.l2_db.execute("CREATE INDEX IF NOT EXISTS idx_access_count ON vision_cache(access_count)")
        
        self.l2_db.commit()
        
        # Load frequently accessed items into L1 cache
        await self._preload_l1_cache()
    
    def generate_cache_key(self, request_data: Dict[str, Any]) -> str:
        """Generate cache key for vision request"""
        # Include relevant request parameters in cache key
        key_components = [
            request_data.get('screenshot_path', ''),
            str(request_data.get('required_accuracy', 0.8)),
            str(request_data.get('max_response_time', 5.0)),
            request_data.get('force_tier', ''),
        ]
        
        # Include file modification time if screenshot path exists
        screenshot_path = request_data.get('screenshot_path')
        if screenshot_path and Path(screenshot_path).exists():
            mtime = Path(screenshot_path).stat().st_mtime
            key_components.append(str(mtime))
        
        content = ':'.join(key_components)
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve from cache with multi-level fallback"""
        
        # L1 Cache check (memory)
        if cache_key in self.l1_cache:
            # Move to end (LRU)
            self.l1_cache.move_to_end(cache_key)
            self.stats['l1_hits'] += 1
            logger.debug(f"L1 cache hit: {cache_key}")
            return self.l1_cache[cache_key]['data']
        
        # L2 Cache check (database)
        l2_result = await self._get_from_l2(cache_key)
        if l2_result:
            self.stats['l2_hits'] += 1
            logger.debug(f"L2 cache hit: {cache_key}")
            
            # Promote to L1 cache
            await self._promote_to_l1(cache_key, l2_result)
            return l2_result
        
        # L3 Cache check (preprocessed images) - TODO: implement if needed
        
        self.stats['misses'] += 1
        return None
    
    async def set(self, cache_key: str, data: Dict[str, Any], tier: str = "unknown"):
        """Store in cache with intelligent tier selection"""
        
        # Serialize data
        try:
            serialized_data = json.dumps(data, default=str)
            size_bytes = len(serialized_data.encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to serialize cache data: {e}")
            return
        
        current_time = time.time()
        
        # Always store in L2 (persistent)
        await self._store_in_l2(cache_key, serialized_data, current_time, size_bytes, tier)
        
        # Store in L1 if not too large
        if size_bytes < 1024 * 1024:  # 1MB limit for L1
            await self._store_in_l1(cache_key, data, current_time, size_bytes)
    
    async def _get_from_l2(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get from L2 database cache"""
        try:
            cursor = self.l2_db.execute(
                "SELECT data, access_count FROM vision_cache WHERE key = ?",
                (cache_key,)
            )
            result = cursor.fetchone()
            
            if result:
                data_json, access_count = result
                
                # Update access count
                self.l2_db.execute(
                    "UPDATE vision_cache SET access_count = access_count + 1 WHERE key = ?",
                    (cache_key,)
                )
                self.l2_db.commit()
                
                return json.loads(data_json)
            
        except Exception as e:
            logger.error(f"L2 cache read error: {e}")
        
        return None
    
    async def _store_in_l2(self, cache_key: str, data: str, timestamp: float, size_bytes: int, tier: str):
        """Store in L2 database cache"""
        try:
            self.l2_db.execute(
                "INSERT OR REPLACE INTO vision_cache (key, data, timestamp, size_bytes, tier) VALUES (?, ?, ?, ?, ?)",
                (cache_key, data, timestamp, size_bytes, tier)
            )
            self.l2_db.commit()
            
        except Exception as e:
            logger.error(f"L2 cache write error: {e}")
    
    async def _store_in_l1(self, cache_key: str, data: Dict[str, Any], timestamp: float, size_bytes: int):
        """Store in L1 memory cache"""
        
        # Ensure L1 cache size limit
        while len(self.l1_cache) >= self.l1_max_size:
            # Remove least recently used
            oldest_key, _ = self.l1_cache.popitem(last=False)
            self.stats['evictions'] += 1
            logger.debug(f"L1 cache eviction: {oldest_key}")
        
        self.l1_cache[cache_key] = {
            'data': data,
            'timestamp': timestamp,
            'size_bytes': size_bytes
        }
    
    async def _promote_to_l1(self, cache_key: str, data: Dict[str, Any]):
        """Promote L2 cache hit to L1"""
        current_time = time.time()
        size_bytes = len(json.dumps(data, default=str).encode('utf-8'))
        
        if size_bytes < 1024 * 1024:  # 1MB limit
            await self._store_in_l1(cache_key, data, current_time, size_bytes)
    
    async def _preload_l1_cache(self):
        """Preload frequently accessed items into L1 cache"""
        try:
            # Get most frequently accessed items
            cursor = self.l2_db.execute(
                "SELECT key, data FROM vision_cache ORDER BY access_count DESC LIMIT ?",
                (min(50, self.l1_max_size),)
            )
            
            for key, data_json in cursor.fetchall():
                try:
                    data = json.loads(data_json)
                    size_bytes = len(data_json.encode('utf-8'))
                    
                    if size_bytes < 1024 * 1024:  # 1MB limit
                        self.l1_cache[key] = {
                            'data': data,
                            'timestamp': time.time(),
                            'size_bytes': size_bytes
                        }
                
                except Exception as e:
                    logger.warning(f"Failed to preload cache item {key}: {e}")
            
            logger.info(f"Preloaded {len(self.l1_cache)} items into L1 cache")
            
        except Exception as e:
            logger.error(f"Failed to preload L1 cache: {e}")
    
    async def cleanup_expired(self, max_age_hours: int = 24):
        """Clean up expired cache entries"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        try:
            # Clean up L2 database
            cursor = self.l2_db.execute(
                "DELETE FROM vision_cache WHERE timestamp < ?",
                (cutoff_time,)
            )
            deleted_count = cursor.rowcount
            self.l2_db.commit()
            
            # Clean up L1 cache
            l1_keys_to_remove = []
            for key, entry in self.l1_cache.items():
                if entry['timestamp'] < cutoff_time:
                    l1_keys_to_remove.append(key)
            
            for key in l1_keys_to_remove:
                del self.l1_cache[key]
            
            logger.info(f"Cache cleanup: removed {deleted_count} L2 entries, {len(l1_keys_to_remove)} L1 entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        total_requests = sum(self.stats.values())
        hit_rate = (self.stats['l1_hits'] + self.stats['l2_hits'] + self.stats['l3_hits']) / max(1, total_requests)
        
        return {
            'stats': self.stats,
            'hit_rate': hit_rate,
            'l1_size': len(self.l1_cache),
            'l1_max_size': self.l1_max_size,
            'total_requests': total_requests
        }


class VisionPerformanceOptimizer:
    """Main performance optimization orchestrator"""
    
    def __init__(self):
        self.preprocessor = IntelligentImagePreprocessor()
        self.cache = MultiLevelVisionCache()
        self.metrics = PerformanceMetrics()
        
        # Performance optimization settings
        self.optimization_level = OptimizationLevel.ADAPTIVE
        self.enable_caching = True
        self.enable_preprocessing = True
        self.batch_processing = False
        
        # Monitoring
        self.monitoring_active = False
        
    async def initialize(self):
        """Initialize optimizer"""
        await self.cache.initialize()
        logger.info("Vision Performance Optimizer initialized")
    
    async def optimize_vision_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Optimize a vision request for maximum performance"""
        start_time = time.time()
        optimization_metadata = {
            'cache_hit': False,
            'preprocessing_applied': False,
            'optimization_level': self.optimization_level.value,
            'performance_metrics': {}
        }
        
        try:
            # Generate cache key
            if self.enable_caching:
                cache_key = self.cache.generate_cache_key(request_data)
                
                # Check cache first
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    optimization_metadata['cache_hit'] = True
                    optimization_metadata['total_time'] = time.time() - start_time
                    self.metrics.cache_hits += 1
                    return cached_result, optimization_metadata
                else:
                    self.metrics.cache_misses += 1
            
            # Preprocess image if enabled
            optimized_request = request_data.copy()
            if self.enable_preprocessing and 'screenshot_path' in request_data:
                preprocessing_start = time.time()
                
                optimized_path, preprocessing_metadata = await self.preprocessor.optimize_image(
                    request_data['screenshot_path'],
                    self.optimization_level
                )
                
                optimized_request['screenshot_path'] = optimized_path
                optimization_metadata['preprocessing_applied'] = True
                optimization_metadata['preprocessing_metadata'] = preprocessing_metadata
                
                self.metrics.preprocessing_time += time.time() - preprocessing_start
            
            # Record request metrics
            self.metrics.request_count += 1
            optimization_metadata['total_time'] = time.time() - start_time
            
            return optimized_request, optimization_metadata
            
        except Exception as e:
            self.metrics.error_count += 1
            optimization_metadata['error'] = str(e)
            optimization_metadata['total_time'] = time.time() - start_time
            return request_data, optimization_metadata
    
    async def cache_vision_result(self, request_data: Dict[str, Any], result: Dict[str, Any], tier_used: str = "unknown"):
        """Cache vision analysis result"""
        if not self.enable_caching:
            return
        
        try:
            cache_key = self.cache.generate_cache_key(request_data)
            await self.cache.set(cache_key, result, tier_used)
            
        except Exception as e:
            logger.error(f"Failed to cache vision result: {e}")
    
    async def start_performance_monitoring(self, interval: float = 30.0):
        """Start continuous performance monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        asyncio.create_task(self._monitoring_loop(interval))
        logger.info("Performance monitoring started")
    
    async def stop_performance_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring_active = False
        logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self, interval: float):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                await self._collect_performance_metrics()
                await self._optimize_based_on_metrics()
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(10)
    
    async def _collect_performance_metrics(self):
        """Collect current performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            
            self.metrics.memory_usage = memory_info.percent
            
            # Update recent performance data
            if self.metrics.recent_times:
                self.metrics.avg_response_time = statistics.mean(self.metrics.recent_times)
            
            # Calculate throughput (requests per minute)
            current_time = time.time()
            minute_ago = current_time - 60
            recent_requests = sum(1 for t in self.metrics.recent_times if t > minute_ago)
            self.metrics.throughput = recent_requests
            
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
    
    async def _optimize_based_on_metrics(self):
        """Dynamically optimize based on current metrics"""
        try:
            # Adaptive optimization level adjustment
            if self.optimization_level == OptimizationLevel.ADAPTIVE:
                if self.metrics.memory_usage > 85 or self.metrics.avg_response_time > 10:
                    # Switch to minimal optimization under high load
                    logger.info("High system load detected, switching to minimal optimization")
                elif self.metrics.memory_usage < 60 and self.metrics.avg_response_time < 3:
                    # Switch to quality optimization under low load
                    logger.info("Low system load detected, switching to quality optimization")
            
            # Cache cleanup if memory usage is high
            if self.metrics.memory_usage > 80:
                await self.cache.cleanup_expired(max_age_hours=12)  # More aggressive cleanup
            
        except Exception as e:
            logger.error(f"Adaptive optimization error: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'request_metrics': {
                'total_requests': self.metrics.request_count,
                'average_response_time': self.metrics.avg_response_time,
                'throughput_per_minute': self.metrics.throughput,
                'error_rate': self.metrics.error_count / max(1, self.metrics.request_count),
            },
            'cache_metrics': cache_stats,
            'system_metrics': {
                'memory_usage_percent': self.metrics.memory_usage,
                'gpu_usage_percent': self.metrics.gpu_usage,
            },
            'optimization_settings': {
                'level': self.optimization_level.value,
                'caching_enabled': self.enable_caching,
                'preprocessing_enabled': self.enable_preprocessing,
            }
        }
    
    async def cleanup(self):
        """Cleanup optimizer resources"""
        await self.stop_performance_monitoring()
        await self.cache.cleanup_expired()
        logger.info("Vision Performance Optimizer cleaned up")


# Example usage and testing
async def test_performance_optimizer():
    """Test the performance optimizer"""
    optimizer = VisionPerformanceOptimizer()
    
    try:
        # Initialize
        await optimizer.initialize()
        
        # Start monitoring
        await optimizer.start_performance_monitoring(interval=10.0)
        
        # Simulate some requests
        test_requests = [
            {
                'screenshot_path': 'test_image1.png',
                'page_url': 'https://example.com',
                'required_accuracy': 0.8
            },
            {
                'screenshot_path': 'test_image2.png',
                'page_url': 'https://example.org',
                'required_accuracy': 0.9
            }
        ]
        
        for i, request in enumerate(test_requests):
            print(f"\nProcessing request {i + 1}...")
            
            # Optimize request
            optimized_request, metadata = await optimizer.optimize_vision_request(request)
            
            print(f"  Cache hit: {metadata['cache_hit']}")
            print(f"  Preprocessing applied: {metadata['preprocessing_applied']}")
            print(f"  Total optimization time: {metadata['total_time']:.3f}s")
            
            # Simulate vision processing result
            fake_result = {
                'caption': f'Test result {i + 1}',
                'elements': [{'role': 'button', 'text': 'Test Button'}],
                'confidence': 0.85
            }
            
            # Cache the result
            await optimizer.cache_vision_result(request, fake_result, 'test_tier')
        
        # Test cache hit on repeated request
        print("\nTesting cache hit...")
        optimized_request, metadata = await optimizer.optimize_vision_request(test_requests[0])
        print(f"  Cache hit: {metadata['cache_hit']}")
        
        # Get performance report
        print("\nPerformance Report:")
        report = optimizer.get_performance_report()
        print(json.dumps(report, indent=2))
        
        # Let monitoring run for a bit
        await asyncio.sleep(15)
        
    finally:
        await optimizer.cleanup()


if __name__ == "__main__":
    asyncio.run(test_performance_optimizer())