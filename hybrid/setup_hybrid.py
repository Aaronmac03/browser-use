"""
Setup script for the Hybrid Local-Vision + Cloud-Reasoning system.

This script helps you configure and test the hybrid implementation.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path

def check_ollama_installed():
    """Check if Ollama is installed and running"""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_minicpm_model():
    """Check if MiniCPM-V 2.6 model is available"""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        return "minicpm-v:2.6" in result.stdout
    except:
        return False

def check_google_api_key():
    """Check if Google API key is set"""
    return bool(os.getenv("GOOGLE_API_KEY"))

async def test_hybrid_components():
    """Test that hybrid components can be imported and initialized"""
    try:
        # Add parent directory to path for imports
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        
        from hybrid.vision_state_builder import VisionStateBuilder
        from hybrid.local_action_heuristics import LocalActionHeuristics
        from hybrid.cloud_planner_client import CloudPlannerClient
        from hybrid.handoff_manager import HandoffManager
        
        print("✅ All hybrid components imported successfully")
        
        # Test basic initialization (without API calls)
        vision_builder = VisionStateBuilder()
        local_heuristics = LocalActionHeuristics()
        
        print("✅ Local components initialized successfully")
        
        # Test cloud client only if API key is available
        if check_google_api_key():
            try:
                cloud_client = CloudPlannerClient(api_key=os.getenv("GOOGLE_API_KEY"))
                print("✅ Cloud client initialized successfully")
            except Exception as e:
                print(f"⚠️  Cloud client initialization warning: {e}")
        else:
            print("⚠️  Google API key not set - cloud client not tested")
        
        return True
    except Exception as e:
        print(f"❌ Error testing hybrid components: {e}")
        return False

def print_setup_instructions():
    """Print setup instructions"""
    print("\n" + "="*60)
    print("HYBRID SYSTEM SETUP INSTRUCTIONS")
    print("="*60)
    
    print("\n1. INSTALL OLLAMA:")
    print("   - Download from: https://ollama.ai/")
    print("   - Install and start Ollama service")
    
    print("\n2. DOWNLOAD MINICPM-V 2.6 MODEL:")
    print("   - Run: ollama pull minicpm-v:2.6")
    print("   - This downloads the local vision model (~4GB)")
    
    print("\n3. SET GOOGLE API KEY:")
    print("   - Get API key from: https://makersuite.google.com/app/apikey")
    print("   - Set environment variable:")
    print("     Windows: set GOOGLE_API_KEY=your_api_key")
    print("     Linux/Mac: export GOOGLE_API_KEY=your_api_key")
    
    print("\n4. VERIFY SETUP:")
    print("   - Run this script again to verify all components")
    print("   - Then run: python basic_example.py")

def main():
    print("🔧 HYBRID SYSTEM SETUP CHECKER")
    print("-" * 40)
    
    # Check Ollama installation
    if check_ollama_installed():
        print("✅ Ollama is installed and running")
    else:
        print("❌ Ollama is not installed or not running")
        print("   Download from: https://ollama.ai/")
    
    # Check MiniCPM-V model
    if check_minicpm_model():
        print("✅ MiniCPM-V 2.6 model is available")
    else:
        print("❌ MiniCPM-V 2.6 model not found")
        print("   Run: ollama pull minicpm-v:2.6")
    
    # Check Google API key
    if check_google_api_key():
        print("✅ Google API key is configured")
    else:
        print("❌ Google API key not found")
        print("   Set GOOGLE_API_KEY environment variable")
    
    # Test hybrid components
    print("\n📦 Testing hybrid components...")
    success = asyncio.run(test_hybrid_components())
    
    if success:
        print("\n🎉 Hybrid system is ready!")
        print("\nNext steps:")
        print("1. Ensure Ollama is running: ollama serve")
        print("2. Run the example: python basic_example.py")
    else:
        print("\n⚠️  Some components need attention")
        print_setup_instructions()

if __name__ == "__main__":
    main()