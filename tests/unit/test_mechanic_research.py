#!/usr/bin/env python3
"""
Test script for the new AI-powered mechanic research functionality.
"""
import asyncio
import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'data_engine'))

from data_engine.commander_recommender import CommanderRecommendationEngine, RecommendationRequest

async def test_mechanic_research():
    """Test the new AI mechanic research feature."""
    print("Testing AI Mechanic Research Feature...")
    
    # Create engine with AI enabled
    engine = CommanderRecommendationEngine(use_ai=True)
    
    # Test with Alela and preferred mechanics
    request = RecommendationRequest(
        commander_name="Alela, Artful Provocateur",
        power_level="focused",
        budget_limit=15.0,
        preferred_mechanics="Flying creatures and artifacts that create tokens, faerie synergies"
    )
    
    print(f"Commander: {request.commander_name}")
    print(f"Preferred Mechanics: {request.preferred_mechanics}")
    print(f"Power Level: {request.power_level}")
    print(f"Budget Limit: ${request.budget_limit}")
    print("\n" + "="*50 + "\n")
    
    try:
        # Generate recommendations
        recommendations = await engine.generate_recommendations(request)
        
        print("Recommendations generated successfully!")
        print(f"Commander: {recommendations.commander.name}")
        print(f"Total recommendations: {len(recommendations.recommendations)}")
        
        # Show top AI-influenced recommendations
        print(f"\nTop 10 Recommendations (with AI influence):")
        for i, rec in enumerate(recommendations.recommendations[:10], 1):
            ai_influenced = "🔥 AI PICK" if any("AI recommended" in reason for reason in (rec.reasons or [])) else ""
            print(f"{i:2d}. {rec.card_name:<30} (Score: {rec.confidence_score:.3f}) {ai_influenced}")
            
            # Show reasons, especially AI ones
            if rec.reasons:
                for reason in rec.reasons:
                    if "AI recommended" in reason:
                        print(f"    {reason}")
                    elif i <= 3:  # Show all reasons for top 3
                        print(f"    • {reason}")
        
        # Count AI-influenced cards
        ai_influenced_count = sum(1 for rec in recommendations.recommendations 
                                if rec.reasons and any("AI recommended" in reason for reason in rec.reasons))
        
        print(f"\nSummary:")
        print(f"   • Total recommendations: {len(recommendations.recommendations)}")
        print(f"   • AI-influenced cards: {ai_influenced_count}")
        print(f"   • Power level: {recommendations.power_level_assessment}")
        
        if recommendations.estimated_total_cost:
            print(f"   • Estimated cost: ${recommendations.estimated_total_cost:.2f}")
        
        print("\nMechanic research test completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mechanic_research())