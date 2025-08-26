#!/usr/bin/env python3
"""Test the availability check directly"""

import asyncio
from vision_module import VisionAnalyzer

async def test():
    analyzer = VisionAnalyzer()
    print("Testing check_ollama_availability()...")
    result = await analyzer.check_ollama_availability()
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test())