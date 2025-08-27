#!/usr/bin/env python3
"""
Structured Data Extraction System
Extracts structured information from web pages and vision analysis
"""

import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
import decimal


class DataType(Enum):
	"""Types of structured data to extract."""
	PRICE = "price"
	DATE = "date"
	AVAILABILITY = "availability"
	CONTACT_INFO = "contact_info"
	ADDRESS = "address"
	PRODUCT_INFO = "product_info"
	FORM_DATA = "form_data"
	RATING = "rating"
	QUANTITY = "quantity"
	PERCENTAGE = "percentage"


@dataclass
class ExtractedData:
	"""Container for extracted structured data."""
	data_type: DataType
	value: Any
	confidence: float
	source: str  # "content", "vision", "combined"
	raw_text: str = ""
	location: Optional[Dict[str, Any]] = None  # Position info if available
	
	def to_dict(self) -> Dict[str, Any]:
		"""Convert to dictionary for JSON serialization."""
		return {
			'data_type': self.data_type.value,
			'value': self.value,
			'confidence': self.confidence,
			'source': self.source,
			'raw_text': self.raw_text,
			'location': self.location
		}


@dataclass  
class ExtractionResult:
	"""Results from structured data extraction."""
	extracted_items: List[ExtractedData] = field(default_factory=list)
	summary: Dict[str, Any] = field(default_factory=dict)
	processing_time: float = 0.0
	errors: List[str] = field(default_factory=list)
	
	def get_by_type(self, data_type: DataType) -> List[ExtractedData]:
		"""Get all extracted data of a specific type."""
		return [item for item in self.extracted_items if item.data_type == data_type]
	
	def get_best_by_type(self, data_type: DataType) -> Optional[ExtractedData]:
		"""Get the highest confidence item of a specific type."""
		items = self.get_by_type(data_type)
		return max(items, key=lambda x: x.confidence) if items else None


class StructuredExtractor:
	"""Extracts structured data from web pages and vision analysis."""
	
	def __init__(self):
		"""Initialize with extraction patterns."""
		# Price patterns with capture groups
		self.price_patterns = [
			(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 'USD'),  # $1,234.56
			(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*USD', 'USD'),  # 1234.56 USD
			(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*dollars?', 'USD'),  # 1234 dollars
			(r'Price:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 'USD'),  # Price: $123.45
			(r'Total:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 'USD'),  # Total: $123.45
			(r'(\d+(?:\.\d{2})?)\s*per\s+night', 'USD'),  # 99.50 per night
		]
		
		# Date patterns
		self.date_patterns = [
			r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',  # MM/DD/YYYY, MM-DD-YYYY
			r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 15, 2024
			r'(\d{1,2}\s+\w+\s+\d{4})',  # 15 January 2024
			r'Check.?in:?\s*([^,\n]+)',  # Check-in: date
			r'Check.?out:?\s*([^,\n]+)',  # Check-out: date
		]
		
		# Availability patterns
		self.availability_patterns = [
			(r'(?i)(in\s+stock)', True),
			(r'(?i)(available)', True),
			(r'(?i)(\d+\s+available)', True),
			(r'(?i)(out\s+of\s+stock)', False),
			(r'(?i)(unavailable)', False),
			(r'(?i)(sold\s+out)', False),
		]
		
		# Contact info patterns
		self.contact_patterns = [
			(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', 'phone'),  # Phone numbers
			(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 'email'),  # Email
		]
		
		# Rating patterns
		self.rating_patterns = [
			r'(\d+(?:\.\d+)?)\s*(?:out\s+of\s+)?(?:stars?|\/5|\*)',  # 4.5 stars, 4/5
			r'Rating:?\s*(\d+(?:\.\d+)?)',  # Rating: 4.5
		]
	
	def _clean_price_value(self, price_str: str) -> float:
		"""Clean and convert price string to float."""
		# Remove currency symbols and commas
		clean_str = re.sub(r'[^\d.]', '', price_str)
		try:
			return float(clean_str)
		except ValueError:
			return 0.0
	
	def _parse_date_string(self, date_str: str) -> Optional[str]:
		"""Parse date string to ISO format."""
		date_str = date_str.strip()
		
		# Try common date formats
		formats = [
			'%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y',
			'%B %d, %Y', '%B %d %Y', '%d %B %Y',
			'%b %d, %Y', '%b %d %Y', '%d %b %Y'
		]
		
		for fmt in formats:
			try:
				parsed_date = datetime.strptime(date_str, fmt).date()
				return parsed_date.isoformat()
			except ValueError:
				continue
		
		return None
	
	async def extract_prices(self, text: str, source: str = "content") -> List[ExtractedData]:
		"""Extract price information from text."""
		extracted = []
		
		for pattern, currency in self.price_patterns:
			matches = re.finditer(pattern, text, re.IGNORECASE)
			for match in matches:
				price_str = match.group(1)
				price_value = self._clean_price_value(price_str)
				
				if price_value > 0:  # Valid price
					confidence = 0.9 if '$' in match.group(0) else 0.7
					
					extracted.append(ExtractedData(
						data_type=DataType.PRICE,
						value={'amount': price_value, 'currency': currency},
						confidence=confidence,
						source=source,
						raw_text=match.group(0),
						location={'start': match.start(), 'end': match.end()}
					))
		
		return extracted
	
	async def extract_dates(self, text: str, source: str = "content") -> List[ExtractedData]:
		"""Extract date information from text."""
		extracted = []
		
		for pattern in self.date_patterns:
			matches = re.finditer(pattern, text, re.IGNORECASE)
			for match in matches:
				date_str = match.group(1)
				parsed_date = self._parse_date_string(date_str)
				
				if parsed_date:
					confidence = 0.8
					
					extracted.append(ExtractedData(
						data_type=DataType.DATE,
						value=parsed_date,
						confidence=confidence,
						source=source,
						raw_text=match.group(0),
						location={'start': match.start(), 'end': match.end()}
					))
		
		return extracted
	
	async def extract_availability(self, text: str, source: str = "content") -> List[ExtractedData]:
		"""Extract availability status from text."""
		extracted = []
		
		for pattern, is_available in self.availability_patterns:
			matches = re.finditer(pattern, text, re.IGNORECASE)
			for match in matches:
				confidence = 0.8
				
				# Extract quantity if present in match
				quantity_match = re.search(r'(\d+)', match.group(0))
				quantity = int(quantity_match.group(1)) if quantity_match else None
				
				value = {
					'available': is_available,
					'quantity': quantity,
					'status_text': match.group(0)
				}
				
				extracted.append(ExtractedData(
					data_type=DataType.AVAILABILITY,
					value=value,
					confidence=confidence,
					source=source,
					raw_text=match.group(0),
					location={'start': match.start(), 'end': match.end()}
				))
		
		return extracted
	
	async def extract_contact_info(self, text: str, source: str = "content") -> List[ExtractedData]:
		"""Extract contact information from text."""
		extracted = []
		
		for pattern, contact_type in self.contact_patterns:
			matches = re.finditer(pattern, text)
			for match in matches:
				confidence = 0.9 if contact_type == 'email' else 0.7
				
				extracted.append(ExtractedData(
					data_type=DataType.CONTACT_INFO,
					value={'type': contact_type, 'value': match.group(0)},
					confidence=confidence,
					source=source,
					raw_text=match.group(0),
					location={'start': match.start(), 'end': match.end()}
				))
		
		return extracted
	
	async def extract_ratings(self, text: str, source: str = "content") -> List[ExtractedData]:
		"""Extract rating information from text."""
		extracted = []
		
		for pattern in self.rating_patterns:
			matches = re.finditer(pattern, text, re.IGNORECASE)
			for match in matches:
				rating_str = match.group(1)
				try:
					rating_value = float(rating_str)
					confidence = 0.8
					
					# Normalize to 5-star scale if needed
					if rating_value > 5:
						rating_value = rating_value / 10 * 5  # Assume 10-point scale
					
					extracted.append(ExtractedData(
						data_type=DataType.RATING,
						value={'rating': rating_value, 'scale': 5},
						confidence=confidence,
						source=source,
						raw_text=match.group(0),
						location={'start': match.start(), 'end': match.end()}
					))
				except ValueError:
					continue
		
		return extracted
	
	async def extract_from_vision_elements(self, vision_state: Dict[str, Any]) -> List[ExtractedData]:
		"""Extract structured data from vision analysis elements."""
		extracted = []
		
		if not vision_state:
			return extracted
		
		# Combine text from all vision sources
		vision_text = vision_state.get('caption', '') + ' '
		
		if 'elements' in vision_state:
			for element in vision_state['elements']:
				if 'visible_text' in element:
					vision_text += element['visible_text'] + ' '
		
		if 'affordances' in vision_state:
			for affordance in vision_state['affordances']:
				if 'label' in affordance:
					vision_text += affordance['label'] + ' '
		
		# Extract all data types from vision text
		source = "vision"
		
		extracted.extend(await self.extract_prices(vision_text, source))
		extracted.extend(await self.extract_dates(vision_text, source))
		extracted.extend(await self.extract_availability(vision_text, source))
		extracted.extend(await self.extract_contact_info(vision_text, source))
		extracted.extend(await self.extract_ratings(vision_text, source))
		
		return extracted
	
	async def extract_structured_data(self, page_content: str = "", 
									vision_state: Dict[str, Any] = None) -> ExtractionResult:
		"""Extract all structured data from page content and vision analysis."""
		start_time = asyncio.get_event_loop().time()
		result = ExtractionResult()
		
		try:
			# Extract from page content
			if page_content:
				result.extracted_items.extend(await self.extract_prices(page_content, "content"))
				result.extracted_items.extend(await self.extract_dates(page_content, "content"))
				result.extracted_items.extend(await self.extract_availability(page_content, "content"))
				result.extracted_items.extend(await self.extract_contact_info(page_content, "content"))
				result.extracted_items.extend(await self.extract_ratings(page_content, "content"))
			
			# Extract from vision analysis
			if vision_state:
				vision_extracted = await self.extract_from_vision_elements(vision_state)
				result.extracted_items.extend(vision_extracted)
			
			# Deduplicate similar items
			result.extracted_items = self._deduplicate_extractions(result.extracted_items)
			
			# Generate summary
			result.summary = self._generate_summary(result.extracted_items)
			
		except Exception as e:
			result.errors.append(f"Extraction error: {str(e)}")
		
		result.processing_time = asyncio.get_event_loop().time() - start_time
		return result
	
	def _deduplicate_extractions(self, extractions: List[ExtractedData]) -> List[ExtractedData]:
		"""Remove duplicate extractions, keeping highest confidence ones."""
		deduped = []
		seen_values = {}
		
		for extraction in sorted(extractions, key=lambda x: x.confidence, reverse=True):
			key = (extraction.data_type, str(extraction.value))
			if key not in seen_values:
				seen_values[key] = True
				deduped.append(extraction)
		
		return deduped
	
	def _generate_summary(self, extractions: List[ExtractedData]) -> Dict[str, Any]:
		"""Generate summary of extracted data."""
		summary = {
			'total_items': len(extractions),
			'by_type': {},
			'by_source': {},
			'high_confidence_items': 0
		}
		
		for extraction in extractions:
			# Count by type
			type_key = extraction.data_type.value
			if type_key not in summary['by_type']:
				summary['by_type'][type_key] = 0
			summary['by_type'][type_key] += 1
			
			# Count by source
			if extraction.source not in summary['by_source']:
				summary['by_source'][extraction.source] = 0
			summary['by_source'][extraction.source] += 1
			
			# High confidence items
			if extraction.confidence >= 0.8:
				summary['high_confidence_items'] += 1
		
		# Extract specific values for common types
		prices = [e.value for e in extractions if e.data_type == DataType.PRICE]
		if prices:
			summary['price_range'] = {
				'min': min(p['amount'] for p in prices),
				'max': max(p['amount'] for p in prices),
				'currency': prices[0]['currency']
			}
		
		dates = [e.value for e in extractions if e.data_type == DataType.DATE]
		if dates:
			summary['date_range'] = {'earliest': min(dates), 'latest': max(dates)}
		
		availability = [e.value for e in extractions if e.data_type == DataType.AVAILABILITY]
		if availability:
			available_count = sum(1 for a in availability if a['available'])
			summary['availability_status'] = {
				'available_items': available_count,
				'unavailable_items': len(availability) - available_count
			}
		
		return summary
	
	def print_extraction_report(self, result: ExtractionResult):
		"""Print formatted extraction report."""
		print("\n" + "="*60)
		print("STRUCTURED DATA EXTRACTION REPORT")
		print("="*60)
		print(f"Processing time: {result.processing_time:.3f}s")
		print(f"Total items extracted: {result.summary.get('total_items', 0)}")
		print(f"High confidence items: {result.summary.get('high_confidence_items', 0)}")
		
		if result.errors:
			print(f"\nErrors: {len(result.errors)}")
			for error in result.errors:
				print(f"  • {error}")
		
		print(f"\nBy data type:")
		for data_type, count in result.summary.get('by_type', {}).items():
			print(f"  {data_type}: {count}")
		
		print(f"\nBy source:")
		for source, count in result.summary.get('by_source', {}).items():
			print(f"  {source}: {count}")
		
		print(f"\nExtracted items:")
		for i, item in enumerate(result.extracted_items[:10], 1):  # Show first 10
			confidence_bar = "█" * int(item.confidence * 10)
			print(f"  {i}. {item.data_type.value}: {item.value}")
			print(f"     Confidence: {confidence_bar} {item.confidence:.2f} | Source: {item.source}")
			if item.raw_text and item.raw_text != str(item.value):
				print(f"     Raw: '{item.raw_text[:50]}{'...' if len(item.raw_text) > 50 else ''}'")
		
		if len(result.extracted_items) > 10:
			print(f"  ... and {len(result.extracted_items) - 10} more items")
		
		# Show summary insights
		if 'price_range' in result.summary:
			price_info = result.summary['price_range']
			print(f"\nPrice range: ${price_info['min']:.2f} - ${price_info['max']:.2f} {price_info['currency']}")
		
		if 'availability_status' in result.summary:
			avail_info = result.summary['availability_status']
			print(f"Availability: {avail_info['available_items']} available, {avail_info['unavailable_items']} unavailable")
		
		print("="*60)


async def test_structured_extraction():
	"""Test the structured data extraction system."""
	extractor = StructuredExtractor()
	
	# Test content
	page_content = """
	Omni Louisville Hotel
	Check-in: September 1, 2025
	Check-out: September 2, 2025
	Room rate: $189.50 per night
	Total: $208.45 (including taxes)
	Available - 3 rooms left
	Rating: 4.2 out of 5 stars
	Contact: (502) 515-6000
	Email: reservations@omnihotels.com
	"""
	
	vision_state = {
		"caption": "Hotel booking page showing $189.50 nightly rate and availability",
		"elements": [
			{"role": "text", "visible_text": "September 1-2, 2025", "confidence": 0.9},
			{"role": "text", "visible_text": "$189.50", "confidence": 0.8},
			{"role": "button", "visible_text": "Book Now - Available", "confidence": 0.9}
		]
	}
	
	# Run extraction
	result = await extractor.extract_structured_data(page_content, vision_state)
	
	# Print report
	extractor.print_extraction_report(result)
	
	# Test getting specific data types
	print("\n" + "="*30)
	print("SPECIFIC DATA QUERIES")
	print("="*30)
	
	prices = result.get_by_type(DataType.PRICE)
	print(f"Found {len(prices)} prices:")
	for price in prices:
		print(f"  ${price.value['amount']:.2f} (confidence: {price.confidence:.2f})")
	
	dates = result.get_by_type(DataType.DATE)
	print(f"\nFound {len(dates)} dates:")
	for date_item in dates:
		print(f"  {date_item.value} (confidence: {date_item.confidence:.2f})")


if __name__ == "__main__":
	asyncio.run(test_structured_extraction())