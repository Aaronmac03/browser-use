#!/usr/bin/env python3
"""Test vision model stability across multiple calls."""

import asyncio
import tempfile
from PIL import Image
from vision_module import VisionAnalyzer
import time

async def test_multiple_calls():
    # Create simple test images
    images = []
    for i in range(5):
        img = Image.new('RGB', (200, 100), color=(255, i*50, 0))  # Different colors
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            img.save(temp_file.name)
            images.append(temp_file.name)
    
    analyzer = VisionAnalyzer()
    
    print("Testing vision stability with aggressive cleanup...")
    print("Changes applied:")
    print("- keep_alive: 0 (fresh model loads)")
    print("- num_ctx: 512 (small context)")
    print("- Connection: close (fresh connections)")  
    print("- Cleanup after each call")
    print("- Preemptive cleanup before calls")
    print()
    
    results = []
    
    for i, image_path in enumerate(images):
        print(f"=== VISION CALL {i+1}/5 ===")
        start_time = time.time()
        
        try:
            result = await analyzer.analyze(image_path)
            duration = time.time() - start_time
            success = True
            print(f"SUCCESS: {duration:.2f}s")
            results.append(('SUCCESS', duration))
        except Exception as e:
            duration = time.time() - start_time  
            print(f"FAILED: {duration:.2f}s - {e}")
            results.append(('TIMEOUT' if 'timeout' in str(e).lower() else 'ERROR', duration))
        
        print()
    
    # Analysis
    print("=== RESULTS ANALYSIS ===")
    successes = [r for r in results if r[0] == 'SUCCESS']
    timeouts = [r for r in results if r[0] == 'TIMEOUT']
    
    print(f"Success rate: {len(successes)}/{len(results)} ({len(successes)/len(results)*100:.1f}%)")
    
    if successes:
        avg_time = sum(r[1] for r in successes) / len(successes)
        print(f"Average success time: {avg_time:.2f}s")
        print(f"Success times: {[f'{r[1]:.2f}s' for r in successes]}")
    
    print(f"Timeouts: {len(timeouts)}")
    
    # Check for degradation pattern
    if len(results) >= 3:
        early_pattern = results[:2]  # First 2 calls
        late_pattern = results[2:]   # Last 3 calls
        
        early_success = sum(1 for r in early_pattern if r[0] == 'SUCCESS') 
        late_success = sum(1 for r in late_pattern if r[0] == 'SUCCESS')
        
        print(f"Early success rate (calls 1-2): {early_success}/{len(early_pattern)}")
        print(f"Late success rate (calls 3-5): {late_success}/{len(late_pattern)}")
        
        if early_success > 0 and late_success == 0:
            print("⚠️ DEGRADATION PATTERN DETECTED - cleanup not working")
        elif early_success == 0 and late_success > 0:
            print("✅ IMPROVEMENT PATTERN - model warming up properly")
        elif early_success > 0 and late_success > 0:
            print("✅ STABLE PATTERN - cleanup working!")
        else:
            print("❌ CONSISTENT FAILURE - deeper issues")
    
    return len(successes) >= 3  # Success if 3+ calls work

if __name__ == "__main__":
    success = asyncio.run(test_multiple_calls())
    exit(0 if success else 1)