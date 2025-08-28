#!/usr/bin/env python3
"""
E2E test for Louisville Omni hotel search using local-first agent.

Tests the complete workflow:
1. Qwen2.5-VL as primary local model
2. Serper API for search optimization 
3. Gemini 2.5 Flash as escalation model
4. Search for hotel availability and pricing

Usage: python test_e2e_hotel_search.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add browser-agent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.models import ModelConfigManager, TaskComplexity
from config.settings import Settings
from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
from models.local_handler import OllamaModelHandler  
from models.cloud_handler import CloudModelManager
from utils.serper import SerperAPI
from utils.logger import setup_logging


class HotelSearchAgent:
	"""E2E agent for hotel search tasks with local-first approach."""
	
	def __init__(self):
		"""Initialize the hotel search agent."""
		self.logger = logging.getLogger(__name__)
		self.settings = Settings()
		
		# Initialize components
		self.model_config_manager = ModelConfigManager()
		self.local_handler = OllamaModelHandler()
		self.cloud_manager = CloudModelManager()
		self.serper_api = SerperAPI(api_key=os.getenv("SERPER_API_KEY", "test-key"))
		
		# Initialize router with local-first strategy
		self.model_router = ModelRouter(
			model_config_manager=self.model_config_manager,
			local_handler=self.local_handler,
			cloud_manager=self.cloud_manager,
			default_strategy=RoutingStrategy.LOCAL_FIRST
		)
		
	async def search_hotel_availability(
		self, 
		hotel_name: str,
		location: str, 
		checkin_date: str,
		checkout_date: str
	) -> Dict[str, Any]:
		"""
		Search for hotel availability and pricing.
		
		Args:
			hotel_name: Name of the hotel
			location: Hotel location
			checkin_date: Check-in date (MM/DD/YY format)
			checkout_date: Check-out date (MM/DD/YY format)
			
		Returns:
			Search results with availability and pricing
		"""
		self.logger.info(f"Starting hotel search: {hotel_name} in {location}")
		self.logger.info(f"Dates: {checkin_date} - {checkout_date}")
		
		# Step 1: Use Serper API to find hotel website and booking info
		search_query = f"{hotel_name} {location} hotel reservations booking {checkin_date} {checkout_date}"
		
		try:
			serper_results = await self.serper_api.search(
				query=search_query,
				search_type="search",
				num_results=5
			)
			self.logger.info(f"Serper API returned {len(serper_results.get('results', []))} results")
			
			# Extract relevant booking URLs and information
			booking_info = self._extract_booking_info(serper_results)
			
		except Exception as e:
			self.logger.error(f"Serper API search failed: {e}")
			booking_info = {"error": str(e)}
		
		# Step 2: Use model router to select appropriate model for analysis
		task_requirements = TaskRequirements(
			complexity=TaskComplexity.MODERATE,
			requires_vision=True,  # For analyzing hotel websites
			requires_code=False,
			max_cost=0.01  # Keep costs low
		)
		
		try:
			selected_model = await self.model_router.select_model(task_requirements)
			self.logger.info(f"Selected model: {selected_model.name} ({selected_model.provider})")
			
			# Step 3: Analyze results with selected model
			analysis_prompt = f"""
			Analyze the following hotel search results for {hotel_name} in {location}:
			
			Search Results: {booking_info}
			
			Requested dates: {checkin_date} to {checkout_date}
			
			Please provide:
			1. Availability status (available/unavailable/unclear)
			2. Room rates if available
			3. Booking instructions or direct links
			4. Alternative dates if unavailable
			5. Special offers or packages
			
			Be concise and factual. Format as structured data.
			"""
			
			# Use local model first (Qwen2.5-VL)
			if selected_model.provider.value == "ollama":
				analysis_result = await self._analyze_with_local_model(
					analysis_prompt, 
					selected_model
				)
			else:
				analysis_result = await self._analyze_with_cloud_model(
					analysis_prompt,
					selected_model  
				)
				
			return {
				"hotel_name": hotel_name,
				"location": location, 
				"checkin_date": checkin_date,
				"checkout_date": checkout_date,
				"search_results": booking_info,
				"selected_model": selected_model.name,
				"analysis": analysis_result,
				"timestamp": datetime.now().isoformat()
			}
			
		except Exception as e:
			self.logger.error(f"Model analysis failed: {e}")
			return {
				"hotel_name": hotel_name,
				"location": location,
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			}
	
	def _extract_booking_info(self, serper_results: Dict[str, Any]) -> Dict[str, Any]:
		"""Extract relevant booking information from Serper results."""
		results = serper_results.get("results", [])
		
		booking_info = {
			"direct_links": [],
			"booking_sites": [],
			"phone_numbers": [],
			"key_info": []
		}
		
		for result in results[:3]:  # Top 3 results
			title = result.get("title", "")
			link = result.get("link", "")
			snippet = result.get("snippet", "")
			
			# Look for direct hotel booking links
			if any(term in title.lower() for term in ["omni", "official", "direct"]):
				booking_info["direct_links"].append({
					"title": title,
					"url": link,
					"snippet": snippet
				})
			
			# Look for booking platforms
			if any(term in link.lower() for term in ["booking.com", "expedia", "hotels.com", "marriott", "hilton"]):
				booking_info["booking_sites"].append({
					"platform": link.split("//")[1].split("/")[0],
					"title": title,
					"url": link
				})
			
			# Extract key information
			booking_info["key_info"].append(snippet)
		
		return booking_info
	
	async def _analyze_with_local_model(
		self, 
		prompt: str, 
		model_config
	) -> Dict[str, Any]:
		"""Analyze with local Ollama model (Qwen2.5-VL)."""
		try:
			if not await self.local_handler.is_model_available(model_config.model_id):
				self.logger.warning(f"Model {model_config.model_id} not available locally")
				raise RuntimeError(f"Local model {model_config.model_id} not available")
			
			response = await self.local_handler.generate_text(
				model_id=model_config.model_id,
				prompt=prompt,
				max_tokens=model_config.max_tokens,
				temperature=model_config.temperature
			)
			
			return {
				"model_used": model_config.name,
				"model_type": "local",
				"response": response,
				"cost": 0.0  # Local models are free
			}
			
		except Exception as e:
			self.logger.error(f"Local model analysis failed: {e}")
			raise
	
	async def _analyze_with_cloud_model(
		self,
		prompt: str,
		model_config
	) -> Dict[str, Any]:
		"""Analyze with cloud model (Gemini 2.5 Flash as escalation)."""
		try:
			response = await self.cloud_manager.generate_text(
				model_config=model_config,
				prompt=prompt,
				max_tokens=model_config.max_tokens,
				temperature=model_config.temperature
			)
			
			# Estimate cost
			input_tokens = len(prompt.split()) * 1.3  # Rough estimate
			output_tokens = len(response.split()) * 1.3
			estimated_cost = model_config.estimate_cost(int(input_tokens), int(output_tokens))
			
			return {
				"model_used": model_config.name,
				"model_type": "cloud", 
				"response": response,
				"estimated_cost": estimated_cost
			}
			
		except Exception as e:
			self.logger.error(f"Cloud model analysis failed: {e}")
			raise


async def test_louisville_omni_search():
	"""Test the Louisville Omni hotel search E2E workflow."""
	print("🏨 Starting Louisville Omni Hotel Search Test")
	print("=" * 60)
	
	# Setup logging
	setup_logging(log_level="INFO")
	
	# Initialize agent
	agent = HotelSearchAgent()
	
	# Test search
	try:
		results = await agent.search_hotel_availability(
			hotel_name="Omni Louisville Hotel",
			location="Louisville, Kentucky", 
			checkin_date="9/2/25",
			checkout_date="9/4/25"
		)
		
		print("\n📊 SEARCH RESULTS:")
		print("-" * 40)
		print(f"Hotel: {results.get('hotel_name')}")
		print(f"Location: {results.get('location')}")
		print(f"Dates: {results.get('checkin_date')} - {results.get('checkout_date')}")
		print(f"Model Used: {results.get('selected_model', 'N/A')}")
		
		if 'error' in results:
			print(f"❌ Error: {results['error']}")
		else:
			analysis = results.get('analysis', {})
			print(f"\n🔍 Analysis:")
			print(f"Model Type: {analysis.get('model_type', 'N/A')}")
			print(f"Cost: ${analysis.get('estimated_cost', 0.0):.4f}")
			print(f"\n💬 Response:")
			print(analysis.get('response', 'No response available'))
			
			# Show search results summary
			search_results = results.get('search_results', {})
			direct_links = search_results.get('direct_links', [])
			if direct_links:
				print(f"\n🔗 Found {len(direct_links)} direct booking links")
				for i, link in enumerate(direct_links[:2], 1):
					print(f"  {i}. {link.get('title', 'No title')}")
		
		print(f"\n⏰ Completed at: {results.get('timestamp')}")
		return results
		
	except Exception as e:
		print(f"❌ Test failed: {e}")
		return None


def main():
	"""Main test runner."""
	print("🤖 Browser-Agent E2E Test")
	print("Local-First Approach: Qwen2.5-VL → Gemini 2.5 Flash → O3 Mini")
	print()
	
	# Check environment
	if not os.getenv("SERPER_API_KEY"):
		print("⚠️  Warning: SERPER_API_KEY not set, using test key")
	
	# Run test
	try:
		results = asyncio.run(test_louisville_omni_search())
		
		if results:
			print("\n✅ Test completed successfully!")
			return 0
		else:
			print("\n❌ Test failed!")
			return 1
			
	except KeyboardInterrupt:
		print("\n🛑 Test interrupted by user")
		return 1
	except Exception as e:
		print(f"\n💥 Unexpected error: {e}")
		return 1


if __name__ == "__main__":
	exit(main())