#!/usr/bin/env python3
"""
Debug Perplexity API responses to see what we're actually getting
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_engine.commander_recommender import CommanderRecommendationEngine
from data_engine.color_identity import ColorIdentity

async def debug_perplexity_response():
    """Test what Perplexity actually returns for our JSON request."""
    engine = CommanderRecommendationEngine(use_ai=True)
    
    if not engine.ai_client:
        print("No AI client available")
        return
    
    print("Testing Perplexity card research...")
    print("=" * 60)
    
    # Test the exact same call the app makes
    try:
        commander_name = "Alela, Artful Provocateur"
        preferred_mechanics = "Flying and artifacts, Token generation, Tribal synergies"
        color_identity = ColorIdentity.from_colors(['W', 'U', 'B'])
        
        result = await engine._research_cards_for_mechanics(
            commander_name,
            preferred_mechanics, 
            color_identity
        )
        
        print(f"Function completed successfully")
        print(f"Returned cards: {result}")
        print(f"Total cards returned: {len(result)}")
        
        if result:
            print("\nSuccessfully extracted cards!")
            for i, card in enumerate(result, 1):
                print(f"{i:2d}. {card}")
        else:
            print("\nWarning: No cards were extracted - this matches what you're seeing")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_perplexity_response())