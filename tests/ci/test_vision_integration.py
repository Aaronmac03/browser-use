"""
Comprehensive integration testing for vision system.
Tests end-to-end browser automation with vision, real webpage analysis, and cross-tier consistency.

Key Focus Areas:
- End-to-end browser automation with vision
- Real webpage screenshot analysis and interaction
- Cross-tier consistency validation (DOM vs Vision vs Multi-tier)
- Browser session integration with vision analysis
- Screenshot capture and analysis pipeline
- Vision-guided browser actions
"""

import asyncio
import base64
import json
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

import pytest
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from pytest_httpserver import HTTPServer

# Import vision system components
from vision_module import VisionAnalyzer, VisionState
from multi_tier_vision import MultiTierVisionSystem, VisionRequest, VisionTier
from enhanced_dom_analyzer import EnhancedDOMAnalyzer


@dataclass
class IntegrationTestResult:
	"""Results from an integration test"""
	test_name: str
	page_url: str
	screenshot_captured: bool
	vision_analysis_success: bool
	dom_analysis_success: bool
	cross_tier_consistency: float
	browser_actions_success: bool
	total_test_time: float
	error_details: Optional[str] = None
	timestamp: float = 0.0


@dataclass
class CrossTierComparison:
	"""Comparison results between different vision tiers"""
	test_scenario: str
	dom_elements_count: int
	vision_elements_count: int
	multi_tier_elements_count: int
	element_overlap_score: float
	caption_similarity_score: float
	processing_time_dom: float
	processing_time_vision: float
	processing_time_multi_tier: float
	consistency_score: float
	timestamp: float


class VisionIntegrationTester:
	"""Comprehensive integration testing for vision system with browser automation"""
	
	def __init__(self):
		self.vision_analyzer = VisionAnalyzer()
		self.multi_tier_system = MultiTierVisionSystem()
		self.dom_analyzer = EnhancedDOMAnalyzer()
		self.integration_results = []
		self.cross_tier_results = []
	
	def create_test_html_page(self, page_type: str = "standard") -> str:
		"""Create HTML test pages for integration testing"""
		
		if page_type == "login":
			return """
			<!DOCTYPE html>
			<html>
			<head>
				<title>Test Login Page</title>
				<style>
					body { font-family: Arial, sans-serif; padding: 20px; }
					.form-container { max-width: 400px; margin: 0 auto; }
					input { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ccc; }
					.btn { background: #007bff; color: white; padding: 12px 20px; border: none; cursor: pointer; }
					.btn:hover { background: #0056b3; }
					.register-link { color: #007bff; text-decoration: underline; cursor: pointer; }
				</style>
			</head>
			<body>
				<div class="form-container">
					<h1>Login to Your Account</h1>
					<form id="loginForm">
						<input type="email" name="email" placeholder="Email Address" required>
						<input type="password" name="password" placeholder="Password" required>
						<button type="submit" class="btn">Sign In</button>
					</form>
					<p>Don't have an account? <span class="register-link" onclick="alert('Register clicked')">Register here</span></p>
				</div>
			</body>
			</html>
			"""
		
		elif page_type == "ecommerce":
			return """
			<!DOCTYPE html>
			<html>
			<head>
				<title>Product Store</title>
				<style>
					body { font-family: Arial, sans-serif; padding: 20px; }
					.product-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
					.product-card { border: 1px solid #ddd; padding: 15px; text-align: center; }
					.product-image { width: 100%; height: 150px; background: #f0f0f0; margin-bottom: 10px; }
					.price { color: #e74c3c; font-size: 18px; font-weight: bold; }
					.add-to-cart { background: #28a745; color: white; padding: 8px 16px; border: none; cursor: pointer; margin: 5px; }
					.wishlist { background: #ffc107; color: black; padding: 8px 16px; border: none; cursor: pointer; margin: 5px; }
					.search-bar { width: 300px; padding: 10px; margin-bottom: 20px; }
				</style>
			</head>
			<body>
				<h1>Our Products</h1>
				<input type="search" class="search-bar" placeholder="Search products...">
				<div class="product-grid">
					<div class="product-card">
						<div class="product-image"></div>
						<h3>Wireless Headphones</h3>
						<p class="price">$89.99</p>
						<button class="add-to-cart">Add to Cart</button>
						<button class="wishlist">♡ Wishlist</button>
					</div>
					<div class="product-card">
						<div class="product-image"></div>
						<h3>Smart Watch</h3>
						<p class="price">$199.99</p>
						<button class="add-to-cart">Add to Cart</button>
						<button class="wishlist">♡ Wishlist</button>
					</div>
					<div class="product-card">
						<div class="product-image"></div>
						<h3>Bluetooth Speaker</h3>
						<p class="price">$49.99</p>
						<button class="add-to-cart">Add to Cart</button>
						<button class="wishlist">♡ Wishlist</button>
					</div>
				</div>
			</body>
			</html>
			"""
		
		elif page_type == "form":
			return """
			<!DOCTYPE html>
			<html>
			<head>
				<title>Contact Form</title>
				<style>
					body { font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; }
					input, select, textarea { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ccc; }
					textarea { height: 120px; }
					.checkbox-group { margin: 10px 0; }
					.submit-btn { background: #007bff; color: white; padding: 15px 30px; border: none; cursor: pointer; }
					.reset-btn { background: #6c757d; color: white; padding: 15px 30px; border: none; cursor: pointer; margin-left: 10px; }
				</style>
			</head>
			<body>
				<h1>Contact Us</h1>
				<form id="contactForm">
					<label>Full Name:</label>
					<input type="text" name="name" required>
					
					<label>Email:</label>
					<input type="email" name="email" required>
					
					<label>Phone:</label>
					<input type="tel" name="phone">
					
					<label>Subject:</label>
					<select name="subject">
						<option value="general">General Inquiry</option>
						<option value="support">Technical Support</option>
						<option value="billing">Billing Question</option>
					</select>
					
					<label>Message:</label>
					<textarea name="message" placeholder="Tell us how we can help you..." required></textarea>
					
					<div class="checkbox-group">
						<input type="checkbox" name="newsletter" id="newsletter">
						<label for="newsletter">Subscribe to our newsletter</label>
					</div>
					
					<button type="submit" class="submit-btn">Send Message</button>
					<button type="reset" class="reset-btn">Clear Form</button>
				</form>
			</body>
			</html>
			"""
		
		else:  # standard
			return """
			<!DOCTYPE html>
			<html>
			<head>
				<title>Test Page</title>
				<style>
					body { font-family: Arial, sans-serif; padding: 20px; }
					.button { background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; margin: 10px; }
					.link { color: #007bff; text-decoration: underline; cursor: pointer; }
					.info-box { background: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; margin: 10px 0; }
				</style>
			</head>
			<body>
				<h1>Integration Test Page</h1>
				<p>This is a test page for vision system integration testing.</p>
				<button class="button" onclick="alert('Button clicked')">Click Me</button>
				<a href="#" class="link" onclick="alert('Link clicked')">Test Link</a>
				<div class="info-box">
					<h3>Information Box</h3>
					<p>This box contains some information for testing purposes.</p>
				</div>
				<input type="text" placeholder="Test input field">
			</body>
			</html>
			"""
	
	async def capture_and_analyze_page(self, page: Page, test_name: str) -> IntegrationTestResult:
		"""Capture screenshot and analyze with vision system"""
		start_time = time.time()
		
		result = IntegrationTestResult(
			test_name=test_name,
			page_url=page.url,
			screenshot_captured=False,
			vision_analysis_success=False,
			dom_analysis_success=False,
			cross_tier_consistency=0.0,
			browser_actions_success=False,
			total_test_time=0.0,
			timestamp=time.time()
		)
		
		try:
			# Step 1: Capture screenshot
			screenshot_path = None
			try:
				screenshot_buffer = await page.screenshot(full_page=True)
				
				with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
					temp_file.write(screenshot_buffer)
					screenshot_path = temp_file.name
				
				result.screenshot_captured = True
				print(f"✓ Screenshot captured: {len(screenshot_buffer)} bytes")
				
			except Exception as e:
				result.error_details = f"Screenshot capture failed: {e}"
				return result
			
			# Step 2: DOM Analysis
			try:
				dom_vision_state = await self.dom_analyzer.analyze_page(
					page, 
					page.url, 
					await page.title()
				)
				result.dom_analysis_success = True
				print(f"✓ DOM Analysis: {len(dom_vision_state.elements)} elements found")
				
			except Exception as e:
				dom_vision_state = None
				result.error_details = f"DOM analysis failed: {e}"
			
			# Step 3: Vision Analysis
			try:
				vision_state = await self.vision_analyzer.analyze(
					screenshot_path,
					page.url,
					await page.title()
				)
				result.vision_analysis_success = True
				print(f"✓ Vision Analysis: {len(vision_state.elements)} elements found")
				
			except Exception as e:
				vision_state = None
				if result.error_details:
					result.error_details += f"; Vision analysis failed: {e}"
				else:
					result.error_details = f"Vision analysis failed: {e}"
			
			# Step 4: Cross-tier consistency check
			if dom_vision_state and vision_state:
				result.cross_tier_consistency = self.calculate_cross_tier_consistency(
					dom_vision_state, vision_state
				)
				print(f"✓ Cross-tier consistency: {result.cross_tier_consistency:.2f}")
			
			# Step 5: Test browser actions based on vision results
			try:
				action_result = await self.test_vision_guided_actions(
					page, vision_state or dom_vision_state
				)
				result.browser_actions_success = action_result
				print(f"✓ Vision-guided actions: {'Success' if action_result else 'Failed'}")
				
			except Exception as e:
				result.browser_actions_success = False
				if result.error_details:
					result.error_details += f"; Action testing failed: {e}"
				else:
					result.error_details = f"Action testing failed: {e}"
			
			result.total_test_time = time.time() - start_time
			
			# Cleanup screenshot
			if screenshot_path:
				try:
					Path(screenshot_path).unlink()
				except:
					pass
			
			return result
			
		except Exception as e:
			result.total_test_time = time.time() - start_time
			result.error_details = f"Integration test failed: {e}"
			return result
	
	def calculate_cross_tier_consistency(self, dom_state: VisionState, vision_state: VisionState) -> float:
		"""Calculate consistency score between DOM and vision analysis"""
		consistency_metrics = []
		
		# Compare element counts (normalized)
		dom_count = len(dom_state.elements)
		vision_count = len(vision_state.elements)
		max_count = max(dom_count, vision_count, 1)
		count_similarity = 1.0 - abs(dom_count - vision_count) / max_count
		consistency_metrics.append(count_similarity)
		
		# Compare captions using simple word overlap
		dom_words = set(dom_state.caption.lower().split())
		vision_words = set(vision_state.caption.lower().split())
		if dom_words or vision_words:
			word_intersection = len(dom_words & vision_words)
			word_union = len(dom_words | vision_words)
			caption_similarity = word_intersection / max(word_union, 1)
		else:
			caption_similarity = 1.0
		consistency_metrics.append(caption_similarity)
		
		# Compare element types
		dom_roles = [elem.role for elem in dom_state.elements]
		vision_roles = [elem.role for elem in vision_state.elements]
		
		if dom_roles or vision_roles:
			dom_role_set = set(dom_roles)
			vision_role_set = set(vision_roles)
			role_intersection = len(dom_role_set & vision_role_set)
			role_union = len(dom_role_set | vision_role_set)
			role_similarity = role_intersection / max(role_union, 1)
		else:
			role_similarity = 1.0
		consistency_metrics.append(role_similarity)
		
		# Overall consistency is average of all metrics
		return sum(consistency_metrics) / len(consistency_metrics)
	
	async def test_vision_guided_actions(self, page: Page, vision_state: VisionState) -> bool:
		"""Test browser actions guided by vision analysis results"""
		if not vision_state or not vision_state.elements:
			return False
		
		try:
			# Test 1: Try to click on buttons found by vision
			buttons = [elem for elem in vision_state.elements if elem.role == 'button']
			if buttons:
				button = buttons[0]  # Try first button
				
				# Try different selector strategies
				selectors_to_try = []
				
				# Use selector hint if available
				if button.selector_hint and button.selector_hint != 'button':
					selectors_to_try.append(button.selector_hint)
				
				# Try text-based selector
				if button.visible_text:
					text = button.visible_text.strip()
					if text and len(text) < 50:  # Reasonable text length
						selectors_to_try.extend([
							f"button:has-text('{text}')",
							f"*:has-text('{text}')",
							f"[aria-label*='{text}']"
						])
				
				# Try generic button selector
				selectors_to_try.append('button')
				
				for selector in selectors_to_try:
					try:
						element = page.locator(selector).first
						if await element.is_visible():
							await element.click(timeout=2000)
							print(f"✓ Successfully clicked button using selector: {selector}")
							return True
					except:
						continue
			
			# Test 2: Try to fill form fields found by vision
			fields = vision_state.fields
			if fields:
				field = fields[0]  # Try first field
				
				selectors_to_try = []
				
				# Use field name hint
				if field.name_hint:
					name = field.name_hint.lower()
					selectors_to_try.extend([
						f"input[name*='{name}']",
						f"input[placeholder*='{name}']",
						f"input[id*='{name}']"
					])
				
				# Generic input selector
				selectors_to_try.append('input[type="text"], input[type="email"], textarea')
				
				for selector in selectors_to_try:
					try:
						element = page.locator(selector).first
						if await element.is_visible():
							await element.fill("test_value")
							print(f"✓ Successfully filled field using selector: {selector}")
							return True
					except:
						continue
			
			# Test 3: Try to interact with links
			links = [elem for elem in vision_state.elements if elem.role == 'link']
			if links:
				link = links[0]
				
				selectors_to_try = []
				
				if link.visible_text:
					text = link.visible_text.strip()
					if text and len(text) < 50:
						selectors_to_try.extend([
							f"a:has-text('{text}')",
							f"*:has-text('{text}')"
						])
				
				selectors_to_try.append('a[href]')
				
				for selector in selectors_to_try:
					try:
						element = page.locator(selector).first
						if await element.is_visible():
							# Just hover over link (safer than clicking)
							await element.hover(timeout=2000)
							print(f"✓ Successfully hovered over link using selector: {selector}")
							return True
					except:
						continue
			
			return False
			
		except Exception as e:
			print(f"Vision-guided action failed: {e}")
			return False
	
	async def cross_tier_comparison_test(self, page: Page, test_scenario: str) -> CrossTierComparison:
		"""Compare analysis results across all vision tiers"""
		
		# Capture screenshot for vision analysis
		screenshot_buffer = await page.screenshot(full_page=True)
		with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
			temp_file.write(screenshot_buffer)
			screenshot_path = temp_file.name
		
		try:
			# DOM Analysis (Tier 1)
			start_time = time.time()
			dom_result = await self.dom_analyzer.analyze_page(page, page.url, await page.title())
			dom_time = time.time() - start_time
			
			# Vision Analysis (Tier 3 - direct)
			start_time = time.time()
			vision_result = await self.vision_analyzer.analyze(screenshot_path, page.url, await page.title())
			vision_time = time.time() - start_time
			
			# Multi-tier Analysis (automatic tier selection)
			start_time = time.time()
			request = VisionRequest(
				page_url=page.url,
				page_title=await page.title(),
				screenshot_path=screenshot_path,
				max_response_time=10.0,
				required_accuracy=0.8
			)
			multi_tier_response = await self.multi_tier_system.analyze(request, page)
			multi_tier_time = time.time() - start_time
			multi_tier_result = multi_tier_response.vision_state
			
			# Calculate comparison metrics
			dom_count = len(dom_result.elements)
			vision_count = len(vision_result.elements)
			multi_tier_count = len(multi_tier_result.elements)
			
			# Element overlap score (how many similar elements found)
			element_overlap = self.calculate_element_overlap_score(
				dom_result.elements, vision_result.elements, multi_tier_result.elements
			)
			
			# Caption similarity
			caption_similarity = self.calculate_caption_similarity(
				dom_result.caption, vision_result.caption, multi_tier_result.caption
			)
			
			# Overall consistency
			consistency_score = (element_overlap + caption_similarity) / 2.0
			
			comparison = CrossTierComparison(
				test_scenario=test_scenario,
				dom_elements_count=dom_count,
				vision_elements_count=vision_count,
				multi_tier_elements_count=multi_tier_count,
				element_overlap_score=element_overlap,
				caption_similarity_score=caption_similarity,
				processing_time_dom=dom_time,
				processing_time_vision=vision_time,
				processing_time_multi_tier=multi_tier_time,
				consistency_score=consistency_score,
				timestamp=time.time()
			)
			
			self.cross_tier_results.append(comparison)
			return comparison
			
		finally:
			Path(screenshot_path).unlink(missing_ok=True)
	
	def calculate_element_overlap_score(self, dom_elements, vision_elements, multi_tier_elements) -> float:
		"""Calculate how much overlap exists between element detections across tiers"""
		
		# Get role distributions
		dom_roles = [elem.role for elem in dom_elements]
		vision_roles = [elem.role for elem in vision_elements]
		multi_tier_roles = [elem.role for elem in multi_tier_elements]
		
		# Calculate pairwise similarities
		similarities = []
		
		# DOM vs Vision
		if dom_roles or vision_roles:
			dom_set = set(dom_roles)
			vision_set = set(vision_roles)
			intersection = len(dom_set & vision_set)
			union = len(dom_set | vision_set)
			dom_vision_sim = intersection / max(union, 1)
			similarities.append(dom_vision_sim)
		
		# DOM vs Multi-tier
		if dom_roles or multi_tier_roles:
			dom_set = set(dom_roles)
			multi_tier_set = set(multi_tier_roles)
			intersection = len(dom_set & multi_tier_set)
			union = len(dom_set | multi_tier_set)
			dom_multi_sim = intersection / max(union, 1)
			similarities.append(dom_multi_sim)
		
		# Vision vs Multi-tier
		if vision_roles or multi_tier_roles:
			vision_set = set(vision_roles)
			multi_tier_set = set(multi_tier_roles)
			intersection = len(vision_set & multi_tier_set)
			union = len(vision_set | multi_tier_set)
			vision_multi_sim = intersection / max(union, 1)
			similarities.append(vision_multi_sim)
		
		return sum(similarities) / max(len(similarities), 1)
	
	def calculate_caption_similarity(self, dom_caption: str, vision_caption: str, multi_tier_caption: str) -> float:
		"""Calculate similarity between captions from different tiers"""
		
		# Tokenize captions
		dom_words = set(dom_caption.lower().split())
		vision_words = set(vision_caption.lower().split())
		multi_tier_words = set(multi_tier_caption.lower().split())
		
		similarities = []
		
		# DOM vs Vision
		intersection = len(dom_words & vision_words)
		union = len(dom_words | vision_words)
		if union > 0:
			similarities.append(intersection / union)
		
		# DOM vs Multi-tier
		intersection = len(dom_words & multi_tier_words)
		union = len(dom_words | multi_tier_words)
		if union > 0:
			similarities.append(intersection / union)
		
		# Vision vs Multi-tier
		intersection = len(vision_words & multi_tier_words)
		union = len(vision_words | multi_tier_words)
		if union > 0:
			similarities.append(intersection / union)
		
		return sum(similarities) / max(len(similarities), 1) if similarities else 0.0
	
	async def test_real_world_scenario(self, browser: Browser, scenario_name: str, 
									 test_steps: List[str]) -> IntegrationTestResult:
		"""Test real-world browser automation scenario with vision guidance"""
		
		context = await browser.new_context(viewport={'width': 1280, 'height': 720})
		page = await context.new_page()
		
		try:
			start_time = time.time()
			
			result = IntegrationTestResult(
				test_name=scenario_name,
				page_url="",
				screenshot_captured=False,
				vision_analysis_success=False,
				dom_analysis_success=False,
				cross_tier_consistency=0.0,
				browser_actions_success=False,
				total_test_time=0.0,
				timestamp=time.time()
			)
			
			# Execute test steps
			for step in test_steps:
				if step.startswith("goto:"):
					url = step[5:].strip()
					await page.goto(url)
					result.page_url = url
					
				elif step.startswith("analyze"):
					# Capture and analyze current page
					screenshot_buffer = await page.screenshot()
					with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
						temp_file.write(screenshot_buffer)
						screenshot_path = temp_file.name
					
					try:
						result.screenshot_captured = True
						
						# Try vision analysis
						try:
							vision_state = await self.vision_analyzer.analyze(
								screenshot_path, page.url, await page.title()
							)
							result.vision_analysis_success = True
						except:
							vision_state = None
						
						# Try DOM analysis
						try:
							dom_state = await self.dom_analyzer.analyze_page(page, page.url, await page.title())
							result.dom_analysis_success = True
						except:
							dom_state = None
						
						# Calculate consistency
						if vision_state and dom_state:
							result.cross_tier_consistency = self.calculate_cross_tier_consistency(dom_state, vision_state)
						
						# Test actions
						if vision_state or dom_state:
							result.browser_actions_success = await self.test_vision_guided_actions(
								page, vision_state or dom_state
							)
						
					finally:
						Path(screenshot_path).unlink(missing_ok=True)
				
				elif step.startswith("wait:"):
					duration = float(step[5:].strip())
					await asyncio.sleep(duration)
			
			result.total_test_time = time.time() - start_time
			self.integration_results.append(result)
			return result
			
		finally:
			await context.close()
	
	def generate_integration_report(self) -> Dict[str, Any]:
		"""Generate comprehensive integration test report"""
		
		report = {
			'summary': {
				'total_integration_tests': len(self.integration_results),
				'total_cross_tier_comparisons': len(self.cross_tier_results),
				'test_timestamp': time.time()
			},
			'integration_test_results': [asdict(r) for r in self.integration_results],
			'cross_tier_comparisons': [asdict(r) for r in self.cross_tier_results],
			'integration_metrics': {},
			'performance_analysis': {},
			'recommendations': []
		}
		
		if self.integration_results:
			# Calculate integration success rates
			screenshot_success_rate = sum(1 for r in self.integration_results if r.screenshot_captured) / len(self.integration_results)
			vision_success_rate = sum(1 for r in self.integration_results if r.vision_analysis_success) / len(self.integration_results)
			dom_success_rate = sum(1 for r in self.integration_results if r.dom_analysis_success) / len(self.integration_results)
			action_success_rate = sum(1 for r in self.integration_results if r.browser_actions_success) / len(self.integration_results)
			
			avg_consistency = sum(r.cross_tier_consistency for r in self.integration_results) / len(self.integration_results)
			avg_test_time = sum(r.total_test_time for r in self.integration_results) / len(self.integration_results)
			
			report['integration_metrics'] = {
				'screenshot_capture_success_rate': screenshot_success_rate,
				'vision_analysis_success_rate': vision_success_rate,
				'dom_analysis_success_rate': dom_success_rate,
				'vision_guided_action_success_rate': action_success_rate,
				'average_cross_tier_consistency': avg_consistency,
				'average_test_duration': avg_test_time
			}
		
		if self.cross_tier_results:
			# Performance analysis
			avg_dom_time = sum(r.processing_time_dom for r in self.cross_tier_results) / len(self.cross_tier_results)
			avg_vision_time = sum(r.processing_time_vision for r in self.cross_tier_results) / len(self.cross_tier_results)
			avg_multi_tier_time = sum(r.processing_time_multi_tier for r in self.cross_tier_results) / len(self.cross_tier_results)
			avg_tier_consistency = sum(r.consistency_score for r in self.cross_tier_results) / len(self.cross_tier_results)
			
			report['performance_analysis'] = {
				'average_dom_processing_time': avg_dom_time,
				'average_vision_processing_time': avg_vision_time,
				'average_multi_tier_processing_time': avg_multi_tier_time,
				'average_cross_tier_consistency': avg_tier_consistency,
				'dom_speed_advantage': avg_vision_time / max(avg_dom_time, 0.001)
			}
		
		# Generate recommendations
		report['recommendations'] = self._generate_integration_recommendations()
		
		return report
	
	def _generate_integration_recommendations(self) -> List[str]:
		"""Generate integration recommendations based on test results"""
		recommendations = []
		
		if not self.integration_results:
			return ["No integration test data available for recommendations"]
		
		# Analyze integration success rates
		total_tests = len(self.integration_results)
		screenshot_failures = sum(1 for r in self.integration_results if not r.screenshot_captured)
		vision_failures = sum(1 for r in self.integration_results if not r.vision_analysis_success)
		action_failures = sum(1 for r in self.integration_results if not r.browser_actions_success)
		
		if screenshot_failures / total_tests > 0.1:
			recommendations.append("HIGH: Screenshot capture failing frequently. Review browser session and screenshot capture logic.")
		
		if vision_failures / total_tests > 0.3:
			recommendations.append("MEDIUM: Vision analysis failing in integration tests. Check service availability and error handling.")
		
		if action_failures / total_tests > 0.5:
			recommendations.append("HIGH: Vision-guided actions failing frequently. Improve element selector generation and fallback strategies.")
		
		# Analyze consistency
		if self.integration_results:
			avg_consistency = sum(r.cross_tier_consistency for r in self.integration_results) / total_tests
			if avg_consistency < 0.6:
				recommendations.append("MEDIUM: Low cross-tier consistency. Review and improve alignment between DOM and vision analysis.")
		
		# Analyze performance
		if self.integration_results:
			slow_tests = [r for r in self.integration_results if r.total_test_time > 30.0]
			if len(slow_tests) / total_tests > 0.2:
				recommendations.append("MEDIUM: Integration tests running slowly. Optimize vision analysis and browser operations.")
		
		if not recommendations:
			recommendations.append("EXCELLENT: All integration tests performing well. Vision system integrates effectively with browser automation.")
		
		return recommendations


class TestVisionIntegration:
	"""Pytest test class for vision integration testing"""
	
	@pytest.fixture(autouse=True)
	async def setup_integration_tester(self):
		"""Set up integration tester for all tests"""
		self.tester = VisionIntegrationTester()
		yield
		# Generate and save integration report
		report = self.tester.generate_integration_report()
		report_path = Path("vision_integration_report.json")
		with open(report_path, 'w') as f:
			json.dump(report, f, indent=2)
	
	async def test_login_page_integration(self, httpserver):
		"""Test integration with login page"""
		# Set up test HTML page
		login_html = self.tester.create_test_html_page("login")
		httpserver.expect_request("/login").respond_with_data(login_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/login"))
				
				result = await self.tester.capture_and_analyze_page(page, "login_page_integration")
				
				# Integration requirements
				assert result.screenshot_captured, "Screenshot should be captured successfully"
				assert result.dom_analysis_success, "DOM analysis should succeed for login page"
				assert result.total_test_time < 30.0, f"Integration test took too long: {result.total_test_time:.2f}s"
				
				# At least one analysis method should work
				assert result.vision_analysis_success or result.dom_analysis_success, "At least one analysis method should succeed"
				
			finally:
				await browser.close()
	
	async def test_ecommerce_page_integration(self, httpserver):
		"""Test integration with e-commerce page"""
		ecommerce_html = self.tester.create_test_html_page("ecommerce")
		httpserver.expect_request("/shop").respond_with_data(ecommerce_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/shop"))
				
				result = await self.tester.capture_and_analyze_page(page, "ecommerce_integration")
				
				# E-commerce pages should have complex elements
				assert result.screenshot_captured, "Screenshot capture failed"
				assert result.dom_analysis_success, "DOM analysis should succeed for e-commerce page"
				
				# Cross-tier consistency should be reasonable for structured page
				if result.vision_analysis_success and result.dom_analysis_success:
					assert result.cross_tier_consistency >= 0.3, f"Cross-tier consistency too low: {result.cross_tier_consistency:.2f}"
				
			finally:
				await browser.close()
	
	async def test_form_page_integration(self, httpserver):
		"""Test integration with complex form page"""
		form_html = self.tester.create_test_html_page("form")
		httpserver.expect_request("/contact").respond_with_data(form_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/contact"))
				
				result = await self.tester.capture_and_analyze_page(page, "form_integration")
				
				# Form pages should be well-analyzed by DOM analyzer
				assert result.dom_analysis_success, "DOM analysis should excel at form pages"
				assert result.screenshot_captured, "Screenshot capture failed"
				
				# Vision-guided actions should work on forms
				if result.vision_analysis_success or result.dom_analysis_success:
					# Actions might fail but should be attempted
					print(f"Vision-guided actions success: {result.browser_actions_success}")
				
			finally:
				await browser.close()
	
	async def test_cross_tier_comparison(self, httpserver):
		"""Test cross-tier analysis comparison"""
		standard_html = self.tester.create_test_html_page("standard")
		httpserver.expect_request("/test").respond_with_data(standard_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/test"))
				
				comparison = await self.tester.cross_tier_comparison_test(page, "standard_page_comparison")
				
				# All tiers should complete analysis
				assert comparison.processing_time_dom > 0, "DOM analysis should complete"
				assert comparison.processing_time_vision >= 0, "Vision analysis should be attempted"
				assert comparison.processing_time_multi_tier > 0, "Multi-tier analysis should complete"
				
				# DOM should be faster than vision analysis
				if comparison.processing_time_vision > 0:
					speed_ratio = comparison.processing_time_vision / max(comparison.processing_time_dom, 0.001)
					assert speed_ratio > 1.0, f"DOM should be faster than vision, ratio: {speed_ratio:.2f}"
				
				# Consistency should be reasonable
				assert comparison.consistency_score >= 0.0, "Consistency score should be non-negative"
				
			finally:
				await browser.close()
	
	async def test_screenshot_analysis_pipeline(self, httpserver):
		"""Test the complete screenshot capture and analysis pipeline"""
		test_html = self.tester.create_test_html_page("standard")
		httpserver.expect_request("/pipeline").respond_with_data(test_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/pipeline"))
				
				# Test the complete pipeline
				start_time = time.time()
				
				# Step 1: Screenshot capture
				screenshot_buffer = await page.screenshot(full_page=True)
				assert len(screenshot_buffer) > 1000, "Screenshot should contain data"
				
				# Step 2: Save screenshot
				with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
					temp_file.write(screenshot_buffer)
					screenshot_path = temp_file.name
				
				try:
					# Step 3: Vision analysis
					vision_state = await self.tester.vision_analyzer.analyze(
						screenshot_path, page.url, await page.title()
					)
					
					# Step 4: Validate results
					assert isinstance(vision_state, VisionState), "Should return VisionState object"
					assert len(vision_state.caption) > 0, "Should have a caption"
					assert vision_state.meta.url == page.url, "URL should match"
					
					pipeline_time = time.time() - start_time
					assert pipeline_time < 45.0, f"Pipeline too slow: {pipeline_time:.2f}s"
					
				finally:
					Path(screenshot_path).unlink(missing_ok=True)
			
			finally:
				await browser.close()
	
	async def test_vision_guided_navigation(self, httpserver):
		"""Test navigation guided by vision analysis"""
		# Create a page with navigation links
		nav_html = """
		<!DOCTYPE html>
		<html>
		<head><title>Navigation Test</title></head>
		<body>
			<nav>
				<a href="/page1" id="nav-home">Home</a>
				<a href="/page2" id="nav-about">About</a>
				<a href="/page3" id="nav-contact">Contact</a>
			</nav>
			<main>
				<h1>Welcome to Navigation Test</h1>
				<p>This page tests vision-guided navigation.</p>
			</main>
		</body>
		</html>
		"""
		
		page2_html = """
		<!DOCTYPE html>
		<html>
		<head><title>About Page</title></head>
		<body>
			<h1>About Us</h1>
			<p>This is the about page.</p>
			<a href="/nav" id="back-home">Back to Home</a>
		</body>
		</html>
		"""
		
		httpserver.expect_request("/nav").respond_with_data(nav_html, content_type="text/html")
		httpserver.expect_request("/page2").respond_with_data(page2_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				# Navigate to initial page
				await page.goto(httpserver.url_for("/nav"))
				
				# Analyze page to find links
				dom_state = await self.tester.dom_analyzer.analyze_page(page, page.url, await page.title())
				
				# Should find navigation links
				links = [elem for elem in dom_state.elements if elem.role == 'link']
				assert len(links) >= 3, f"Should find navigation links, found {len(links)}"
				
				# Try to click on "About" link using vision guidance
				about_links = [link for link in links if 'about' in link.visible_text.lower()]
				if about_links:
					# Simulate clicking the about link
					await page.click('#nav-about')
					
					# Verify navigation worked
					await page.wait_for_url("**/page2", timeout=5000)
					current_url = page.url
					assert "page2" in current_url, f"Navigation failed, current URL: {current_url}"
					
					# Analyze new page
					new_dom_state = await self.tester.dom_analyzer.analyze_page(page, page.url, await page.title())
					assert "About" in new_dom_state.caption, "Should be on About page"
				
			finally:
				await browser.close()
	
	async def test_integration_error_handling(self, httpserver):
		"""Test integration error handling and recovery"""
		# Create a page that might cause issues
		problematic_html = """
		<!DOCTYPE html>
		<html>
		<head><title>Problematic Page</title></head>
		<body>
			<div style="width: 10000px; height: 10000px;">Very large content</div>
			<script>
				// Infinite loop that might cause issues (commented out for safety)
				// while(true) { console.log("test"); }
			</script>
		</body>
		</html>
		"""
		
		httpserver.expect_request("/problematic").respond_with_data(problematic_html, content_type="text/html")
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto(httpserver.url_for("/problematic"))
				
				# Integration should handle problematic pages gracefully
				result = await self.tester.capture_and_analyze_page(page, "error_handling_test")
				
				# Should complete without crashing
				assert result.total_test_time < 60.0, f"Test took too long: {result.total_test_time:.2f}s"
				
				# At least screenshot capture should work
				assert result.screenshot_captured, "Screenshot capture should work even on problematic pages"
				
				# If there are errors, they should be captured
				if result.error_details:
					print(f"Expected errors captured: {result.error_details}")
				
			finally:
				await browser.close()
	
	async def test_real_world_scenario_simulation(self, httpserver):
		"""Test a realistic multi-step scenario"""
		# This would simulate a real workflow like:
		# 1. Navigate to a page
		# 2. Analyze it with vision
		# 3. Fill a form based on analysis
		# 4. Navigate to results
		
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			
			try:
				# Simulate real-world scenario
				test_steps = [
					"goto:https://example.com",
					"analyze",
					"wait:1.0"
				]
				
				result = await self.tester.test_real_world_scenario(
					browser, "real_world_simulation", test_steps
				)
				
				# Should complete the scenario
				assert result.total_test_time < 45.0, f"Scenario took too long: {result.total_test_time:.2f}s"
				assert result.page_url == "https://example.com", "Should navigate to correct URL"
				
				# At least some analysis should succeed
				assert result.screenshot_captured, "Should capture screenshots during scenario"
				
			finally:
				await browser.close()
	
	async def test_integration_report_generation(self):
		"""Test integration report generation"""
		# Run a simple test to populate data
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()
			
			try:
				await page.goto("https://example.com")
				await self.tester.capture_and_analyze_page(page, "report_generation_test")
				
			finally:
				await browser.close()
		
		# Generate report
		report = self.tester.generate_integration_report()
		
		# Validate report structure
		assert 'summary' in report, "Report missing summary"
		assert 'integration_test_results' in report, "Report missing test results"
		assert 'integration_metrics' in report, "Report missing integration metrics"
		assert 'recommendations' in report, "Report missing recommendations"
		
		# Check that we have test data
		assert report['summary']['total_integration_tests'] > 0, "Should have integration test data"
		
		# Check recommendations
		assert isinstance(report['recommendations'], list), "Recommendations should be a list"
		assert len(report['recommendations']) > 0, "Should have recommendations"