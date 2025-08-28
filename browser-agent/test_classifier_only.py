"""
Simple test for Action Classifier component only.
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.action_classifier import ActionClassifier, ActionType, TaskComplexity

# Test scenarios for action classification
TEST_SCENARIOS = [
    # Text-only scenarios (should not require vision)
    {
        "description": "Navigate to https://google.com",
        "has_dom_state": False,
        "expected_vision": False,
        "category": "navigation"
    },
    {
        "description": "Click element with index 5",
        "has_dom_state": True,
        "expected_vision": False,
        "category": "dom_interaction"
    },
    {
        "description": "Input text 'username' into element 3",
        "has_dom_state": True,
        "expected_vision": False,
        "category": "form_filling"
    },
    {
        "description": "Send keys Ctrl+F to search",
        "has_dom_state": False,
        "expected_vision": False,
        "category": "keyboard"
    },
    {
        "description": "Scroll down the page",
        "has_dom_state": False,
        "expected_vision": False,
        "category": "scrolling"
    },
    {
        "description": "Select dropdown option 'United States' from element 7",
        "has_dom_state": True,
        "expected_vision": False,
        "category": "dropdown"
    },
    
    # Vision scenarios (should require vision)
    {
        "description": "Find the blue login button",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "visual_search"
    },
    {
        "description": "Click the search button in the top right corner",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "visual_navigation"
    },
    {
        "description": "Locate the red 'Delete' button",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "visual_search"
    },
    {
        "description": "Identify all visible form fields on the page",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "analysis"
    },
    {
        "description": "Look for the shopping cart icon",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "icon_search"
    },
    
    # Complex scenarios (may require vision and escalation)
    {
        "description": "Analyze this e-commerce page and find the cheapest laptop under $1000",
        "has_dom_state": False,
        "expected_vision": True,
        "category": "complex_analysis"
    },
    {
        "description": "If the login fails, try recovering the account, otherwise create a new one",
        "has_dom_state": True,
        "expected_vision": False,
        "category": "conditional_logic"
    }
]

def setup_logging():
    """Setup basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )

async def test_action_classifier():
    """Test the action classifier component."""
    logger = logging.getLogger(__name__)
    logger.info("=== Testing Action Classifier ===")
    
    classifier = ActionClassifier()
    results = []
    
    print(f"{'Category':<18} | {'Vision':<7} | {'Expected':<8} | {'Match':<5} | {'Type':<18} | {'Complexity':<10} | {'Confidence':<10}")
    print("=" * 90)
    
    for scenario in TEST_SCENARIOS:
        analysis = classifier.classify_action(
            scenario["description"],
            scenario["has_dom_state"]
        )
        
        # Check if classification matches expectations
        vision_match = analysis.requires_vision == scenario["expected_vision"]
        
        result = {
            "scenario": scenario["description"][:50] + "...",
            "category": scenario["category"],
            "expected_vision": scenario["expected_vision"],
            "actual_vision": analysis.requires_vision,
            "vision_match": vision_match,
            "action_type": analysis.action_type.value,
            "complexity": analysis.complexity.value,
            "confidence": analysis.confidence_score
        }
        results.append(result)
        
        status = "✅" if vision_match else "❌"
        
        print(f"{scenario['category']:<18} | {analysis.requires_vision!s:<7} | {scenario['expected_vision']!s:<8} | {status:<5} | {analysis.action_type.value:<18} | {analysis.complexity.value:<10} | {analysis.confidence_score:<10.2f}")
    
    print("\n" + "=" * 90)
    
    # Calculate accuracy
    correct = sum(1 for r in results if r["vision_match"])
    accuracy = correct / len(results) * 100
    logger.info(f"Vision Classification Accuracy: {accuracy:.1f}% ({correct}/{len(results)})")
    
    # Get statistics
    analyses = [
        classifier.classify_action(s["description"], s["has_dom_state"]) 
        for s in TEST_SCENARIOS
    ]
    stats = classifier.get_stats(analyses)
    
    logger.info(f"Vision required: {stats['vision_percentage']:.1f}% ({stats['vision_required']}/{stats['total_tasks']})")
    logger.info(f"Text only: {stats['text_only_percentage']:.1f}% ({stats['text_only']}/{stats['total_tasks']})")
    logger.info(f"Average confidence: {stats['average_confidence']:.2f}")
    
    print("\nAction Type Distribution:")
    for action_type, count in stats['action_types'].items():
        percentage = (count / stats['total_tasks']) * 100
        print(f"  {action_type:<20}: {count:2} ({percentage:4.1f}%)")
    
    print("\nComplexity Distribution:")
    for complexity, count in stats['complexity_distribution'].items():
        percentage = (count / stats['total_tasks']) * 100
        print(f"  {complexity:<10}: {count:2} ({percentage:4.1f}%)")
    
    return results

def main():
    """Run the classifier test."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Testing Action Classifier for Three-Tier Routing")
    logger.info("This test validates vision requirement detection for browser automation tasks")
    
    try:
        results = asyncio.run(test_action_classifier())
        
        # Summary
        logger.info("\n🎯 Test Summary:")
        if results:
            vision_correct = sum(1 for r in results if r["vision_match"])
            classifier_accuracy = vision_correct / len(results) * 100
            logger.info(f"  ✅ Action Classifier: {classifier_accuracy:.1f}% accuracy")
            
            if classifier_accuracy >= 85:
                logger.info("  🚀 Classifier is performing well and ready for integration!")
            elif classifier_accuracy >= 70:
                logger.info("  ⚠️  Classifier needs some tuning but shows promise")
            else:
                logger.info("  ❌ Classifier needs significant improvement")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    main()