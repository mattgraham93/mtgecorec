#!/usr/bin/env python3
"""Test the new super-explicit Perplexity prompts."""

# Test the new extraction with various formats

def test_extraction_formats():
    """Test all our new extraction formats."""
    
    # Test content for delimited format
    delimited_content = """
    Some random text here...
    
    CARDS_START
    Skullclamp
    Sol Ring
    Arcane Signet
    Command Tower
    Rhystic Study
    CARDS_END
    
    More random text...
    """
    
    # Test content for CSV format
    csv_content = """
    Here are the recommendations:
    Skullclamp,Sol Ring,Arcane Signet,Command Tower,Rhystic Study,Smothering Tithe,Cyclonic Rift,Swords to Plowshares
    That's my recommendation.
    """
    
    # Test content for numbered format
    numbered_content = """
    Here's my list:
    
    1. Skullclamp
    2. Sol Ring  
    3. Arcane Signet
    4. Command Tower
    5. Rhystic Study
    6. Smothering Tithe
    7. Cyclonic Rift
    8. Swords to Plowshares
    9. Path to Exile
    10. Counterspell
    
    Those are the cards.
    """
    
    import sys
    sys.path.append('/workspaces/mtgecorec')
    from data_engine.commander_recommender import CommanderRecommendationEngine
    
    engine = CommanderRecommendationEngine(use_ai=False)
    
    print("Testing new extraction formats...\n")
    
    print("1. Testing delimited format (CARDS_START/CARDS_END):")
    print(f"Content: {delimited_content[:100]}...")
    cards = engine._extract_cards_from_json(delimited_content)
    print(f"Extracted: {cards}\n")
    
    print("2. Testing CSV format:")
    print(f"Content: {csv_content[:100]}...")
    cards = engine._extract_cards_from_json(csv_content)
    print(f"Extracted: {cards}\n")
    
    print("3. Testing numbered format:")
    print(f"Content: {numbered_content[:100]}...")
    cards = engine._extract_cards_from_json(numbered_content)
    print(f"Extracted: {cards}\n")

if __name__ == "__main__":
    test_extraction_formats()