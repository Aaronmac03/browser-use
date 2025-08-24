"""
Simple test to verify hybrid components work.
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all hybrid components can be imported"""
    try:
        from hybrid import VisionStateBuilder, LocalActionHeuristics, CloudPlannerClient, HandoffManager
        print("✅ All hybrid components imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_initialization():
    """Test basic initialization of components"""
    try:
        from hybrid import VisionStateBuilder, LocalActionHeuristics, CloudPlannerClient, HandoffManager
        
        # Test local components (no external dependencies)
        vision_builder = VisionStateBuilder()
        local_heuristics = LocalActionHeuristics()
        print("✅ Local components initialized successfully")
        
        # Test cloud component only if API key is available
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            try:
                cloud_client = CloudPlannerClient(api_key=google_api_key)
                print("✅ Cloud client initialized successfully")
            except Exception as e:
                print(f"⚠️  Cloud client warning: {e}")
        else:
            print("⚠️  GOOGLE_API_KEY not set - skipping cloud client test")
            
        return True
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        return False

def main():
    print("🧪 TESTING HYBRID IMPLEMENTATION")
    print("-" * 40)
    
    if test_imports():
        if test_initialization():
            print("\n🎉 Hybrid system components are working!")
            print("\nNext steps:")
            print("1. Install Ollama: https://ollama.ai/")
            print("2. Download model: ollama pull minicpm-v:2.6")
            print("3. Set GOOGLE_API_KEY environment variable")
            print("4. Run: cd hybrid && python basic_example.py")
        else:
            print("\n⚠️  Components imported but initialization failed")
    else:
        print("\n❌ Component imports failed")

if __name__ == "__main__":
    main()