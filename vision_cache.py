#!/usr/bin/env python3
"""
Vision Response Caching System
Reduces redundant analysis by caching vision responses based on image similarity
"""

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import sqlite3
import threading
from datetime import datetime, timedelta


@dataclass 
class CacheEntry:
	"""Vision cache entry with metadata."""
	image_hash: str
	prompt_hash: str
	response: Dict[str, Any]
	confidence: float
	timestamp: float
	access_count: int
	last_accessed: float
	processing_time: float
	model_variant: str


class VisionCache:
	"""Intelligent caching system for vision analysis responses."""
	
	def __init__(self, cache_dir: str = "vision_cache", max_entries: int = 1000,
				max_age_hours: int = 24, similarity_threshold: float = 0.95):
		"""Initialize vision cache.
		
		Args:
			cache_dir: Directory to store cache database
			max_entries: Maximum number of cached entries
			max_age_hours: Maximum age of cache entries in hours
			similarity_threshold: Minimum image similarity for cache hit (0-1)
		"""
		self.cache_dir = Path(cache_dir)
		self.cache_dir.mkdir(exist_ok=True)
		
		self.db_path = self.cache_dir / "vision_cache.db"
		self.max_entries = max_entries
		self.max_age_hours = max_age_hours
		self.similarity_threshold = similarity_threshold
		
		# Thread safety
		self._lock = threading.RLock()
		
		# Performance tracking
		self.stats = {
			'hits': 0,
			'misses': 0,
			'saves': 0,
			'evictions': 0,
			'similarity_checks': 0
		}
		
		self._init_database()
	
	def _init_database(self):
		"""Initialize SQLite database for cache storage."""
		with sqlite3.connect(self.db_path) as conn:
			conn.execute('''
				CREATE TABLE IF NOT EXISTS vision_cache (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					image_hash TEXT NOT NULL,
					prompt_hash TEXT NOT NULL,
					response_json TEXT NOT NULL,
					confidence REAL NOT NULL,
					timestamp REAL NOT NULL,
					access_count INTEGER DEFAULT 1,
					last_accessed REAL NOT NULL,
					processing_time REAL NOT NULL,
					model_variant TEXT NOT NULL,
					UNIQUE(image_hash, prompt_hash)
				)
			''')
			
			# Create indices for fast lookup
			conn.execute('CREATE INDEX IF NOT EXISTS idx_hashes ON vision_cache(image_hash, prompt_hash)')
			conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON vision_cache(timestamp)')
			conn.execute('CREATE INDEX IF NOT EXISTS idx_last_accessed ON vision_cache(last_accessed)')
	
	def _calculate_image_hash(self, image_path: str, resize_for_hash: bool = True) -> str:
		"""Calculate perceptual hash of image for similarity comparison."""
		try:
			from PIL import Image
			import imagehash
			
			img = Image.open(image_path)
			
			# Use perceptual hash for similarity detection
			phash = imagehash.phash(img, hash_size=16)  # Higher resolution hash
			return str(phash)
			
		except ImportError:
			# Fallback to file hash if perceptual hashing not available
			with open(image_path, 'rb') as f:
				return hashlib.md5(f.read()).hexdigest()
	
	def _calculate_prompt_hash(self, prompt: str) -> str:
		"""Calculate hash of normalized prompt."""
		# Normalize prompt (lowercase, strip whitespace)
		normalized = prompt.lower().strip()
		return hashlib.sha256(normalized.encode()).hexdigest()[:16]
	
	def _calculate_similarity(self, hash1: str, hash2: str) -> float:
		"""Calculate similarity between two perceptual hashes."""
		try:
			import imagehash
			
			# Convert string hashes back to imagehash objects
			h1 = imagehash.hex_to_hash(hash1)
			h2 = imagehash.hex_to_hash(hash2)
			
			# Calculate Hamming distance and convert to similarity
			hamming_distance = h1 - h2
			max_distance = len(hash1) * 4  # Maximum possible distance
			similarity = 1.0 - (hamming_distance / max_distance)
			
			return similarity
			
		except (ImportError, ValueError):
			# Fallback: exact match only
			return 1.0 if hash1 == hash2 else 0.0
	
	async def get(self, image_path: str, prompt: str, model_variant: str = "default") -> Optional[Dict[str, Any]]:
		"""Retrieve cached response if available."""
		with self._lock:
			image_hash = self._calculate_image_hash(image_path)
			prompt_hash = self._calculate_prompt_hash(prompt)
			
			# First try exact match
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.execute('''
					SELECT response_json, confidence, access_count, processing_time
					FROM vision_cache 
					WHERE image_hash = ? AND prompt_hash = ? AND model_variant = ?
					ORDER BY timestamp DESC LIMIT 1
				''', (image_hash, prompt_hash, model_variant))
				
				row = cursor.fetchone()
				if row:
					# Update access statistics
					conn.execute('''
						UPDATE vision_cache 
						SET access_count = access_count + 1, last_accessed = ?
						WHERE image_hash = ? AND prompt_hash = ? AND model_variant = ?
					''', (time.time(), image_hash, prompt_hash, model_variant))
					
					self.stats['hits'] += 1
					
					try:
						response = json.loads(row[0])
						response['cached'] = True
						response['cache_confidence'] = row[1]
						response['cache_access_count'] = row[2] + 1
						response['original_processing_time'] = row[3]
						return response
					except json.JSONDecodeError:
						pass
			
			# Try similarity-based matching for same prompt
			if self.similarity_threshold < 1.0:
				self.stats['similarity_checks'] += 1
				
				with sqlite3.connect(self.db_path) as conn:
					cursor = conn.execute('''
						SELECT image_hash, response_json, confidence, access_count, processing_time
						FROM vision_cache 
						WHERE prompt_hash = ? AND model_variant = ?
						ORDER BY timestamp DESC LIMIT 20
					''', (prompt_hash, model_variant))
					
					for row in cursor:
						cached_image_hash = row[0]
						similarity = self._calculate_similarity(image_hash, cached_image_hash)
						
						if similarity >= self.similarity_threshold:
							# Update access statistics for similar match
							conn.execute('''
								UPDATE vision_cache 
								SET access_count = access_count + 1, last_accessed = ?
								WHERE image_hash = ? AND prompt_hash = ? AND model_variant = ?
							''', (time.time(), cached_image_hash, prompt_hash, model_variant))
							
							self.stats['hits'] += 1
							
							try:
								response = json.loads(row[1])
								response['cached'] = True
								response['cache_similarity'] = similarity
								response['cache_confidence'] = row[2]
								response['cache_access_count'] = row[3] + 1
								response['original_processing_time'] = row[4]
								return response
							except json.JSONDecodeError:
								continue
			
			self.stats['misses'] += 1
			return None
	
	async def put(self, image_path: str, prompt: str, response: Dict[str, Any], 
				 confidence: float, processing_time: float, model_variant: str = "default"):
		"""Store response in cache."""
		with self._lock:
			image_hash = self._calculate_image_hash(image_path)
			prompt_hash = self._calculate_prompt_hash(prompt)
			
			# Remove cached flag if present
			clean_response = {k: v for k, v in response.items() 
							if not k.startswith('cache')}
			
			try:
				response_json = json.dumps(clean_response)
			except (TypeError, ValueError):
				print(f"[VisionCache] Failed to serialize response for caching")
				return
			
			current_time = time.time()
			
			with sqlite3.connect(self.db_path) as conn:
				try:
					conn.execute('''
						INSERT OR REPLACE INTO vision_cache 
						(image_hash, prompt_hash, response_json, confidence, 
						 timestamp, last_accessed, processing_time, model_variant)
						VALUES (?, ?, ?, ?, ?, ?, ?, ?)
					''', (image_hash, prompt_hash, response_json, confidence,
						 current_time, current_time, processing_time, model_variant))
					
					self.stats['saves'] += 1
					
				except sqlite3.Error as e:
					print(f"[VisionCache] Database error: {e}")
			
			# Cleanup old entries if needed
			await self._cleanup_if_needed()
	
	async def _cleanup_if_needed(self):
		"""Clean up old or excess cache entries."""
		current_time = time.time()
		cutoff_time = current_time - (self.max_age_hours * 3600)
		
		with sqlite3.connect(self.db_path) as conn:
			# Remove expired entries
			cursor = conn.execute('DELETE FROM vision_cache WHERE timestamp < ?', (cutoff_time,))
			expired_count = cursor.rowcount
			
			if expired_count > 0:
				self.stats['evictions'] += expired_count
				print(f"[VisionCache] Evicted {expired_count} expired entries")
			
			# Check if we need to remove excess entries
			cursor = conn.execute('SELECT COUNT(*) FROM vision_cache')
			total_entries = cursor.fetchone()[0]
			
			if total_entries > self.max_entries:
				# Remove oldest entries beyond limit
				excess = total_entries - self.max_entries
				cursor = conn.execute('''
					DELETE FROM vision_cache 
					WHERE id IN (
						SELECT id FROM vision_cache 
						ORDER BY last_accessed ASC 
						LIMIT ?
					)
				''', (excess,))
				
				removed = cursor.rowcount
				self.stats['evictions'] += removed
				print(f"[VisionCache] Evicted {removed} least recently used entries")
	
	async def clear(self):
		"""Clear all cache entries."""
		with self._lock:
			with sqlite3.connect(self.db_path) as conn:
				conn.execute('DELETE FROM vision_cache')
			
			# Reset stats
			self.stats = {key: 0 for key in self.stats}
			print("[VisionCache] Cache cleared")
	
	async def get_stats(self) -> Dict[str, Any]:
		"""Get cache performance statistics."""
		with self._lock:
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.execute('SELECT COUNT(*) FROM vision_cache')
				total_entries = cursor.fetchone()[0]
				
				cursor = conn.execute('SELECT AVG(access_count) FROM vision_cache')
				avg_access_count = cursor.fetchone()[0] or 0
			
			total_requests = self.stats['hits'] + self.stats['misses']
			hit_rate = (self.stats['hits'] / total_requests) if total_requests > 0 else 0
			
			return {
				'total_entries': total_entries,
				'hit_rate': hit_rate,
				'avg_access_count': avg_access_count,
				'similarity_threshold': self.similarity_threshold,
				**self.stats
			}
	
	def print_stats(self):
		"""Print formatted cache statistics."""
		stats = asyncio.run(self.get_stats())
		
		print("\n" + "="*40)
		print("VISION CACHE STATISTICS")
		print("="*40)
		print(f"Total entries: {stats['total_entries']}")
		print(f"Hit rate: {stats['hit_rate']:.1%}")
		print(f"Hits: {stats['hits']}")
		print(f"Misses: {stats['misses']}")
		print(f"Saves: {stats['saves']}")
		print(f"Evictions: {stats['evictions']}")
		print(f"Similarity checks: {stats['similarity_checks']}")
		print(f"Avg access count: {stats['avg_access_count']:.1f}")
		print(f"Similarity threshold: {stats['similarity_threshold']:.2f}")
		print("="*40)


class CachedVisionAnalyzer:
	"""VisionAnalyzer wrapper with intelligent caching."""
	
	def __init__(self, base_analyzer, cache: VisionCache):
		"""Initialize with base analyzer and cache."""
		self.base_analyzer = base_analyzer
		self.cache = cache
	
	async def analyze(self, screenshot_path: str, page_url: str = "", 
					 page_title: str = "", include_affordances: bool = True):
		"""Analyze with caching support."""
		
		# Generate cache key from analysis parameters
		prompt = self.base_analyzer.build_vision_prompt()
		model_variant = getattr(self.base_analyzer, 'model_name', 'default') or 'default'
		
		# Try to get from cache first
		cached_result = await self.cache.get(screenshot_path, prompt, model_variant)
		if cached_result is not None:
			print(f"[CachedVisionAnalyzer] Cache hit (similarity: {cached_result.get('cache_similarity', 1.0):.2f})")
			
			# Reconstruct VisionState from cached response
			from vision_module_llamacpp import VisionState
			
			# Update metadata with current context
			if 'meta' in cached_result:
				cached_result['meta']['url'] = page_url
				cached_result['meta']['title'] = page_title
				cached_result['meta']['timestamp'] = datetime.now().isoformat()
			
			try:
				return VisionState(**cached_result)
			except Exception as e:
				print(f"[CachedVisionAnalyzer] Failed to reconstruct from cache: {e}")
				# Fall through to fresh analysis
		
		# Perform fresh analysis
		print("[CachedVisionAnalyzer] Cache miss, performing fresh analysis")
		start_time = time.time()
		
		result = await self.base_analyzer.analyze(
			screenshot_path, page_url, page_title, include_affordances
		)
		
		processing_time = time.time() - start_time
		
		# Cache the result
		try:
			result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
			await self.cache.put(
				screenshot_path, prompt, result_dict, 
				result.meta.confidence, processing_time, model_variant
			)
		except Exception as e:
			print(f"[CachedVisionAnalyzer] Failed to cache result: {e}")
		
		return result


async def test_vision_cache():
	"""Test the vision caching system."""
	cache = VisionCache(max_entries=10, max_age_hours=1)
	
	# Create a test image
	test_image = "test_cache_image.png"
	from quantization_benchmark import VisionBenchmarker
	benchmarker = VisionBenchmarker()
	await benchmarker.create_test_image(test_image)
	
	test_prompt = "Describe what you see in this image"
	test_response = {
		"caption": "Test image with buttons and text",
		"elements": [],
		"confidence": 0.8
	}
	
	print("Testing vision cache...")
	
	# Test cache miss
	result = await cache.get(test_image, test_prompt)
	print(f"Cache miss: {result is None}")
	
	# Test cache put
	await cache.put(test_image, test_prompt, test_response, 0.8, 1.5)
	print("Stored in cache")
	
	# Test cache hit
	result = await cache.get(test_image, test_prompt)
	print(f"Cache hit: {result is not None}")
	print(f"Cached response: {result.get('caption', 'N/A')}")
	
	# Print stats
	cache.print_stats()
	
	# Cleanup
	await cache.clear()


if __name__ == "__main__":
	asyncio.run(test_vision_cache())