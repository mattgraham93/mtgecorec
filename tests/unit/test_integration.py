#!/usr/bin/env python3
"""
Integration test for the improved AI card extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_engine.commander_recommender import CommanderRecommendationEngine

def test_improved_card_extraction():
    """Test the improved card extraction with real-world examples."""
    engine = CommanderRecommendationEngine(use_ai=False)
    
    print("Testing Improved Card Extraction")
    print("=" * 50)
    
    # Test JSON extraction
    print("\n1. Testing JSON extraction:")
    json_response = '''
    {
        "recommended_cards": [
            "Skullclamp",
            "Sol Ring", 
            "Smothering Tithe",
            "Lightning Greaves"
        ]
    }
    '''
    
    json_cards = engine._extract_cards_from_json(json_response)
    print(f"   Extracted: {json_cards}")
    assert len(json_cards) == 4
    assert "Skullclamp" in json_cards
    print("   JSON extraction working")
    
    # Test text extraction
    print("\n2. Testing text extraction:")
    text_response = '''
    Here are the best cards for Alela:
    
    1. **Skullclamp** - Amazing card draw
    2. **Sol Ring** - Best ramp artifact
    3. **Lightning Greaves** - Protection and haste
    '''
    
    text_cards = engine._extract_cards_from_text(text_response)
    print(f"   Extracted: {text_cards}")
    assert "Skullclamp" in text_cards
    assert "Sol Ring" in text_cards
    print("   Text extraction working")
    
    # Test card matching
    print("\n3. Testing database matching:")
    ai_suggestions = ["skullclamp", "SOL RING", "Lightning Greavs"]  # Mixed case + typo
    db_cards = ["Skullclamp", "Sol Ring", "Lightning Greaves", "Esper Sentinel"]
    
    matches = engine._match_cards_in_database(ai_suggestions, db_cards)
    print(f"   Matches: {matches}")
    assert len(matches) == 3  # Should match all 3 despite case/typo issues
    print("   Database matching working")
    
    print("\nAll integration tests passed!")
    print("\nThe improved system should now:")
    print("• Parse JSON responses from Perplexity")
    print("• Fall back to text parsing if needed") 
    print("• Match cards regardless of case")
    print("• Handle minor typos with fuzzy matching")
    print("• Filter out non-card phrases")

if __name__ == "__main__":
    test_improved_card_extraction()