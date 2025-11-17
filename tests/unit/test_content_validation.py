#!/usr/bin/env python3
"""Test content validation for MTG vs non-MTG content."""

import sys
sys.path.append('/workspaces/mtgecorec')
from data_engine.commander_recommender import CommanderRecommendationEngine

def test_content_validation():
    """Test MTG content validation."""
    
    engine = CommanderRecommendationEngine(use_ai=False)
    
    # Test cases
    test_cases = [
        # Good MTG content
        ("MTG content 1", "Magic: The Gathering Commander deck with artifacts and flying creatures", True),
        ("MTG content 2", "Alela commander synergizes with tokens and tribal spells", True),
        ("MTG content 3", "Skullclamp provides card draw for your deck", True),
        
        # Bad programming content (like what we got)
        ("Programming content 1", "# 2.3 - Print cards as card names (not numbers). If you want to go for an extra challenge though you could add in some if statements", False),
        ("Programming content 2", "function solution with multiple if or case statements, those are ugly", False),
        ("Programming content 3", "Python code tutorial with variables and loops", False),
    ]
    
    print("🧪 Testing MTG content validation...\n")
    
    for name, content, expected in test_cases:
        result = engine._is_mtg_related_content(content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {name}: {result} (expected {expected})")
        print(f"   Content: {content[:80]}...")
        print()
    
    print("🎯 Testing with actual bad response we got:")
    bad_response = """# 2.3 - Print cards as card names (not numbers)

If you want to go for an extra challenge though you could add in some if statements to print out a nicer form like "6 of diamonds, jack of hearts" instead.

I just thought I'd share my solution to this. While it

*can*, of course, be done with multiple... `if` or

`case` statements, those are ugly, so I tried to do without them."""
    
    result = engine._is_mtg_related_content(bad_response)
    print(f"Bad response validation: {result} (should be False)")

if __name__ == "__main__":
    test_content_validation()