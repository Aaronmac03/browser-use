#!/usr/bin/env python3
"""
Quantization Performance Benchmark Suite
Tests F16 vs Q4_K_M vs Q5_K_M model variants for speed/quality balance
"""

import asyncio
import time
import json
import statistics
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
import hashlib

from llama_cpp_manager import LlamaCppManager
from vision_module_llamacpp import VisionAnalyzer, _to_base64_jpeg


@dataclass
class BenchmarkResult:
	"""Results from a single model benchmark run."""
	model_variant: str
	avg_response_time: float
	min_response_time: float
	max_response_time: float
	median_response_time: float
	std_response_time: float
	success_rate: float
	quality_score: float  # 0-1 based on response completeness
	memory_usage_mb: Optional[float] = None
	throughput_tokens_per_sec: Optional[float] = None


@dataclass
class QuantizationBenchmark:
	"""Complete benchmark results across all quantization levels."""
	test_image_hash: str
	test_prompt: str
	runs_per_variant: int
	results: Dict[str, BenchmarkResult]
	recommendation: str
	timestamp: str


class VisionBenchmarker:
	"""Benchmarks different quantization levels for vision models."""
	
	def __init__(self, endpoint: str = "http://localhost:8080"):
		self.endpoint = endpoint
		self.manager = LlamaCppManager(endpoint=endpoint)
		self.test_prompts = [
			"Describe what you see in this screenshot in detail",
			"List all interactive elements (buttons, links, forms) visible in this image",
			"What is the main purpose of this webpage based on the screenshot?",
			"Identify any pricing information, product details, or form fields"
		]
	
	async def create_test_image(self, output_path: str = "test_screenshot.png") -> str:
		"""Create or use existing test screenshot for benchmarking."""
		# For now, we'll assume a test image exists or create a simple one
		test_path = Path(output_path)
		
		if not test_path.exists():
			# Create a simple test image using PIL if available
			try:
				from PIL import Image, ImageDraw, ImageFont
				
				# Create a mock webpage screenshot
				img = Image.new('RGB', (800, 600), color='white')
				draw = ImageDraw.Draw(img)
				
				# Add some mock webpage elements
				draw.rectangle([50, 50, 750, 100], outline='gray', fill='lightblue')
				draw.text((60, 65), "Mock Webpage Header", fill='black')
				
				draw.rectangle([50, 150, 200, 200], outline='blue', fill='lightgreen')
				draw.text((60, 170), "Search Button", fill='black')
				
				draw.rectangle([250, 150, 400, 200], outline='red', fill='lightyellow')
				draw.text((260, 170), "Add to Cart", fill='black')
				
				draw.text((50, 250), "Product: Test Item - $19.99", fill='black')
				draw.text((50, 280), "Available: In Stock", fill='green')
				
				img.save(test_path)
				print(f"Created test image: {test_path}")
				
			except ImportError:
				print("PIL not available, using placeholder")
				test_path.write_text("placeholder")
		
		return str(test_path)
	
	def _calculate_quality_score(self, response: str, prompt: str) -> float:
		"""Calculate quality score based on response completeness and relevance."""
		if not response or len(response.strip()) < 10:
			return 0.0
		
		# Basic quality heuristics
		score = 0.0
		
		# Length bonus (up to 0.3)
		score += min(len(response) / 500.0, 0.3)
		
		# Keyword relevance (up to 0.4)
		keywords = ['button', 'link', 'text', 'image', 'form', 'click', 'input', 'price', 'product']
		found_keywords = sum(1 for kw in keywords if kw.lower() in response.lower())
		score += (found_keywords / len(keywords)) * 0.4
		
		# JSON structure bonus for structured prompts (up to 0.3)
		if 'json' in prompt.lower() and ('{' in response and '}' in response):
			try:
				json.loads(response.strip())
				score += 0.3  # Valid JSON
			except:
				score += 0.1  # Contains JSON-like structure
		
		return min(score, 1.0)
	
	async def benchmark_model_variant(self, model_path: str, variant_name: str, 
									test_image_path: str, runs: int = 5) -> BenchmarkResult:
		"""Benchmark a specific model quantization variant."""
		print(f"\nBenchmarking {variant_name} ({runs} runs)...")
		
		# Ensure server is running with this model
		analyzer = VisionAnalyzer(endpoint=self.endpoint, model_path=model_path)
		
		if not await analyzer.check_server_availability():
			# Try to start server with this model
			success = await self.manager.ensure_server_running(model_path=model_path)
			if not success:
				raise RuntimeError(f"Failed to start server with {variant_name}")
		
		# Convert test image once
		image_b64 = _to_base64_jpeg(test_image_path)
		
		response_times = []
		success_count = 0
		quality_scores = []
		
		for run in range(runs):
			print(f"  Run {run + 1}/{runs}...", end=" ", flush=True)
			
			# Use different prompts to test various capabilities
			prompt = self.test_prompts[run % len(self.test_prompts)]
			
			start_time = time.time()
			try:
				result = await analyzer._call_llama_cpp_vision(image_b64, prompt, timeout=60.0)
				elapsed = time.time() - start_time
				
				if "error" not in result:
					response_times.append(elapsed)
					success_count += 1
					quality_score = self._calculate_quality_score(result.get("content", ""), prompt)
					quality_scores.append(quality_score)
					print(f"✓ {elapsed:.2f}s (quality: {quality_score:.2f})")
				else:
					print(f"✗ Error: {result['error']}")
			
			except Exception as e:
				print(f"✗ Exception: {str(e)}")
			
			# Small delay between runs
			await asyncio.sleep(1)
		
		# Calculate statistics
		if response_times:
			return BenchmarkResult(
				model_variant=variant_name,
				avg_response_time=statistics.mean(response_times),
				min_response_time=min(response_times),
				max_response_time=max(response_times),
				median_response_time=statistics.median(response_times),
				std_response_time=statistics.stdev(response_times) if len(response_times) > 1 else 0.0,
				success_rate=success_count / runs,
				quality_score=statistics.mean(quality_scores) if quality_scores else 0.0
			)
		else:
			return BenchmarkResult(
				model_variant=variant_name,
				avg_response_time=float('inf'),
				min_response_time=float('inf'),
				max_response_time=float('inf'),
				median_response_time=float('inf'),
				std_response_time=0.0,
				success_rate=0.0,
				quality_score=0.0
			)
	
	def _make_recommendation(self, results: Dict[str, BenchmarkResult]) -> str:
		"""Make a recommendation based on benchmark results."""
		valid_results = {k: v for k, v in results.items() if v.success_rate > 0}
		
		if not valid_results:
			return "No models completed successfully. Check server configuration."
		
		# Calculate composite scores (speed + quality + reliability)
		scored_models = []
		for name, result in valid_results.items():
			# Normalize response time (faster = better)
			max_time = max(r.avg_response_time for r in valid_results.values())
			speed_score = 1.0 - (result.avg_response_time / max_time)
			
			# Composite score: 40% speed, 35% quality, 25% reliability
			composite = (speed_score * 0.4) + (result.quality_score * 0.35) + (result.success_rate * 0.25)
			scored_models.append((name, result, composite))
		
		# Sort by composite score
		scored_models.sort(key=lambda x: x[2], reverse=True)
		
		best_model = scored_models[0]
		recommendation = f"Recommended: {best_model[0]} "
		recommendation += f"(composite score: {best_model[2]:.3f}, "
		recommendation += f"avg time: {best_model[1].avg_response_time:.2f}s, "
		recommendation += f"quality: {best_model[1].quality_score:.2f}, "
		recommendation += f"reliability: {best_model[1].success_rate:.1%})"
		
		return recommendation
	
	async def run_full_benchmark(self, model_variants: Dict[str, str], 
								runs_per_variant: int = 3) -> QuantizationBenchmark:
		"""Run complete benchmark across all quantization variants."""
		print("Starting Vision Model Quantization Benchmark")
		print("=" * 50)
		
		# Create test image
		test_image = await self.create_test_image()
		
		# Calculate test image hash for reproducibility
		with open(test_image, 'rb') as f:
			image_hash = hashlib.md5(f.read()).hexdigest()[:8]
		
		results = {}
		
		for variant_name, model_path in model_variants.items():
			try:
				result = await self.benchmark_model_variant(
					model_path, variant_name, test_image, runs_per_variant
				)
				results[variant_name] = result
			except Exception as e:
				print(f"Failed to benchmark {variant_name}: {e}")
				# Create failed result
				results[variant_name] = BenchmarkResult(
					model_variant=variant_name,
					avg_response_time=float('inf'),
					min_response_time=float('inf'),
					max_response_time=float('inf'),
					median_response_time=float('inf'),
					std_response_time=0.0,
					success_rate=0.0,
					quality_score=0.0
				)
		
		# Generate recommendation
		recommendation = self._make_recommendation(results)
		
		benchmark = QuantizationBenchmark(
			test_image_hash=image_hash,
			test_prompt="Mixed prompts for comprehensive testing",
			runs_per_variant=runs_per_variant,
			results=results,
			recommendation=recommendation,
			timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
		)
		
		# Save results
		results_file = Path("quantization_benchmark_results.json")
		with open(results_file, 'w') as f:
			# Convert dataclasses to dict for JSON serialization
			data = {
				'test_image_hash': benchmark.test_image_hash,
				'test_prompt': benchmark.test_prompt,
				'runs_per_variant': benchmark.runs_per_variant,
				'results': {k: asdict(v) for k, v in benchmark.results.items()},
				'recommendation': benchmark.recommendation,
				'timestamp': benchmark.timestamp
			}
			json.dump(data, f, indent=2)
		
		print(f"\nBenchmark results saved to: {results_file}")
		return benchmark
	
	def print_results_table(self, benchmark: QuantizationBenchmark):
		"""Print formatted results table."""
		print("\n" + "=" * 80)
		print("QUANTIZATION BENCHMARK RESULTS")
		print("=" * 80)
		print(f"Test Date: {benchmark.timestamp}")
		print(f"Runs per variant: {benchmark.runs_per_variant}")
		print(f"Test image hash: {benchmark.test_image_hash}")
		
		print("\nResults:")
		print("-" * 80)
		print(f"{'Model':<12} {'Avg Time':<10} {'Success':<8} {'Quality':<8} {'Min/Max':<12}")
		print("-" * 80)
		
		for name, result in benchmark.results.items():
			if result.success_rate > 0:
				print(f"{name:<12} {result.avg_response_time:<10.2f} "
					 f"{result.success_rate:<8.1%} {result.quality_score:<8.2f} "
					 f"{result.min_response_time:.1f}/{result.max_response_time:.1f}")
			else:
				print(f"{name:<12} {'FAILED':<10} {result.success_rate:<8.1%} "
					 f"{result.quality_score:<8.2f} {'N/A':<12}")
		
		print("-" * 80)
		print(f"RECOMMENDATION: {benchmark.recommendation}")
		print("=" * 80)


async def main():
	"""Run the quantization benchmark with common model variants."""
	benchmarker = VisionBenchmarker()
	
	# Define model variants to test (adjust paths as needed)
	model_variants = {
		"F16": "models/moondream2.gguf",  # Full precision
		"Q5_K_M": "models/moondream2-q5_k_m.gguf",  # High quality quantized
		"Q4_K_M": "models/moondream2-q4_k_m.gguf",  # Balanced quantized
	}
	
	# Check which models actually exist
	available_variants = {}
	for name, path in model_variants.items():
		if Path(path).exists():
			available_variants[name] = path
		else:
			print(f"⚠ Model not found: {path}")
	
	if not available_variants:
		print("No model variants found. Please ensure models are in the 'models/' directory:")
		for name, path in model_variants.items():
			print(f"  {name}: {path}")
		return
	
	print(f"Found {len(available_variants)} model variants:")
	for name in available_variants:
		print(f"  ✓ {name}")
	
	# Run benchmark
	benchmark = await benchmarker.run_full_benchmark(available_variants, runs_per_variant=3)
	
	# Print results
	benchmarker.print_results_table(benchmark)


if __name__ == "__main__":
	asyncio.run(main())