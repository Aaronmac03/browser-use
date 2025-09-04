#!/usr/bin/env python3
"""
Privacy-First Data Extraction Workflow

This example demonstrates:
- Large-scale data extraction with local processing
- Structured data output and analysis
- GTX 1660 Ti optimization for bulk operations
- Privacy preservation during web scraping

Use Case: Market research, competitive analysis, data collection
Perfect for: Researchers, analysts, data scientists
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from hybrid_orchestrator import HybridOrchestrator, HybridConfig
from enhanced_local_llm import LocalLLMConfig
from cloud_planner import CloudPlannerConfig
from runner import make_browser, build_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def tech_company_data_extraction():
	"""
	Example: Extract structured data about tech companies.
	
	Showcases:
	- Systematic data collection across multiple pages
	- Structured output formatting
	- Privacy-first processing (data never leaves your machine)
	- Optimized batch processing
	"""
	
	print("\n📊 TECH COMPANY DATA EXTRACTION")
	print("=" * 50)
	print("Systematic Data Collection with Privacy Preservation")
	print("Structured Output + Local Processing")
	print()
	
	# Optimized config for data extraction
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=4096,      # Large context for data processing
			temperature=0.1,      # Very precise for data extraction
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=3,  # Strategic planning for data collection
			enable_serper=True     # Enhanced search capabilities
		),
		local_first_threshold=0.92,  # High privacy standard
		performance_monitoring=True
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	# Data extraction task
	extraction_task = """
	Extract structured data about emerging AI startups in 2024:
	
	1. Search for "AI startups 2024 funding rounds" and find 5-7 companies
	
	2. For each company found, collect:
	   - Company name
	   - Headquarters location  
	   - Founding year
	   - Latest funding round (amount and date if available)
	   - Primary AI focus (NLP, computer vision, etc.)
	   - Key products or services
	   - Employee count estimate (if available)
	   - Website URL
	
	3. Structure the data in JSON format for each company:
	   {
	     "name": "Company Name",
	     "location": "City, State/Country", 
	     "founded": "YYYY",
	     "funding": {
	       "latest_round": "Series A/B/Seed",
	       "amount": "$X million",
	       "date": "Month YYYY"
	     },
	     "focus_area": "Primary AI domain",
	     "products": ["Product 1", "Product 2"],
	     "employees": "estimate",
	     "website": "https://..."
	   }
	
	4. Create a summary analysis:
	   - Most common AI focus areas
	   - Average funding amounts
	   - Geographic distribution
	   - Trends in founding years
	
	Focus on factual, publicly available information only.
	"""
	
	print(f"🎯 Target: Extract data for 5-7 AI startups")
	print(f"📊 Output: Structured JSON + Analysis")
	print(f"🔒 Privacy: {config.local_first_threshold:.0%}+ local processing")
	print()
	
	try:
		# Execute data extraction
		result = await orchestrator.execute_task(
			extraction_task,
			browser,
			tools,
			include_thinking=True,
			max_actions_per_step=20,  # More actions for data collection
			step_delay=0.3  # Respectful scraping delays
		)
		
		print("\n📊 EXTRACTION RESULTS")
		print("=" * 30)
		print(f"✅ Success: {result['success']}")
		print(f"⏱️  Duration: {result['total_time']:.1f}s")  
		print(f"🔄 Steps: {len(result['results'])}")
		
		print(f"\n🔒 PRIVACY METRICS")
		print("=" * 30)
		print(f"☁️  Cloud Usage: {result['cloud_usage']['planning_calls_used']}/{result['cloud_usage']['max_planning_calls']} calls")
		print(f"🖥️  Local Processing: {result['local_processing_ratio']:.1%}")
		print(f"🛡️  Data Security: All extracted data processed locally")
		
		print(f"\n⚡ EXTRACTION PERFORMANCE")
		print("=" * 30)
		print(f"🎯 Success Rate: {result['local_performance']['success_rate']:.1%}")
		print(f"📈 Avg Step Time: {result['local_performance']['avg_step_time']:.1f}s")
		print(f"🚀 GTX 1660 Ti Optimized: Q4_K_M quantization active")
		
		# Show extraction insights
		if result['results']:
			print(f"\n📋 STEP BREAKDOWN")
			print("=" * 30)
			for i, step_result in enumerate(result['results'], 1):
				status = "✅" if step_result['success'] else "❌"
				duration = step_result.get('duration', 0)
				print(f"{status} Step {i}: {duration:.1f}s")
		
		return result
		
	except Exception as e:
		logger.error(f"Data extraction failed: {e}")
		return None
		
	finally:
		await browser.kill()
		print(f"\n🏁 Data extraction completed!")

async def product_price_monitoring():
	"""
	Example: Monitor product prices across multiple e-commerce sites.
	Demonstrates comparative data extraction.
	"""
	
	print("\n💰 PRODUCT PRICE MONITORING")
	print("=" * 40)
	print("Multi-site price comparison extraction")
	print()
	
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=2048,
			temperature=0.1
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=2,
			enable_serper=True
		),
		local_first_threshold=0.95  # High privacy for shopping data
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	# Price monitoring task
	price_task = """
	Compare prices for "gaming laptop GTX 1660 Ti" across sites:
	
	1. Search on 2-3 major e-commerce sites (Amazon, Newegg, Best Buy)
	2. Find 3-5 gaming laptops with GTX 1660 Ti
	3. Extract for each laptop:
	   - Model name
	   - Brand  
	   - Current price
	   - Original price (if on sale)
	   - Rating/review count
	   - Key specs (RAM, storage, CPU)
	   - Site name
	
	4. Create price comparison table showing:
	   - Lowest price for similar specs
	   - Best value (price/performance ratio)
	   - Price ranges across sites
	
	Focus on current publicly available pricing only.
	"""
	
	try:
		result = await orchestrator.execute_task(
			price_task,
			browser,
			tools,
			max_actions_per_step=15
		)
		
		print(f"💰 Price monitoring: {'✅ Complete' if result['success'] else '❌ Issues'}")
		print(f"🔒 Shopping privacy: {result['local_processing_ratio']:.0%} local")
		print(f"⚡ Performance: {result['total_time']:.1f}s")
		
		return result
		
	except Exception as e:
		logger.error(f"Price monitoring failed: {e}")
		return None
		
	finally:
		await browser.kill()

async def job_market_analysis():
	"""
	Example: Extract job market data for AI/ML positions.  
	Shows large-scale structured data collection.
	"""
	
	print("\n💼 JOB MARKET ANALYSIS")
	print("=" * 35)
	print("AI/ML job market data extraction")
	print()
	
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=3072,
			temperature=0.1
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=3,
			enable_serper=True
		),
		local_first_threshold=0.9
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	job_analysis_task = """
	Analyze AI/ML job market trends:
	
	1. Search job sites for "Machine Learning Engineer" positions
	2. Collect data from 10-15 job postings:
	   - Job title variations
	   - Company size/type  
	   - Required skills (top 5 most common)
	   - Experience level requirements
	   - Location (remote vs on-site)
	   - Salary range (if listed)
	
	3. Create market analysis:
	   - Most in-demand skills
	   - Geographic hotspots
	   - Experience level distribution
	   - Remote work availability
	   - Average requirements per job
	
	Focus on recent postings (last 30 days) for current market trends.
	"""
	
	try:
		result = await orchestrator.execute_task(
			job_analysis_task,
			browser,
			tools,
			max_actions_per_step=18,
			step_delay=0.5
		)
		
		print(f"💼 Job analysis: {'✅ Complete' if result['success'] else '❌ Issues'}")
		print(f"📊 Market insights: {len(result['results'])} analysis steps")
		print(f"🔒 Privacy: {result['local_processing_ratio']:.0%} local processing")
		
		return result
		
	except Exception as e:
		logger.error(f"Job analysis failed: {e}")
		return None
		
	finally:
		await browser.kill()

async def save_extraction_results(results: List[Dict], filename: str):
	"""Save extraction results to JSON file."""
	try:
		output_file = Path(__file__).parent / f"output_{filename}.json"
		with open(output_file, 'w') as f:
			json.dump(results, f, indent=2)
		
		print(f"📁 Results saved to: {output_file}")
		return output_file
		
	except Exception as e:
		logger.error(f"Failed to save results: {e}")
		return None

async def main():
	"""Run data extraction workflow examples."""
	print("🚀 PRIVACY-FIRST DATA EXTRACTION EXAMPLES")
	print("Local processing + structured outputs")
	print()
	
	results = []
	
	# Run tech company data extraction
	tech_result = await tech_company_data_extraction() 
	if tech_result:
		results.append({"workflow": "tech_companies", "result": tech_result})
	
	await asyncio.sleep(2)
	
	# Run price monitoring
	price_result = await product_price_monitoring()
	if price_result:
		results.append({"workflow": "price_monitoring", "result": price_result})
	
	await asyncio.sleep(2)
	
	# Run job market analysis
	job_result = await job_market_analysis()
	if job_result:
		results.append({"workflow": "job_analysis", "result": job_result})
	
	# Save all results
	if results:
		await save_extraction_results(results, "data_extraction_workflows")
	
	print("\n🎉 All data extraction examples completed!")
	print("🔒 All extracted data processed locally")
	print("📊 Structured outputs saved for analysis")
	print("💡 Tip: Modify extraction fields for your specific needs")

if __name__ == "__main__":
	asyncio.run(main())