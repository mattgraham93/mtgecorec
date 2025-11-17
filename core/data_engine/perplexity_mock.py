"""
Mock Perplexity client for development when API is unavailable
"""
import os
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class MockPerplexityClient:
    """Mock client that provides sample responses when the real API is unavailable."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('PERPLEXITY_API_KEY')
        self.mock_mode = True
        
    def analyze_commander_synergies(self, commander_name: str, card_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """Mock analysis for commander synergies."""
        
        # Sample response for Atraxa
        if "atraxa" in commander_name.lower():
            analysis = """
# Atraxa, Praetors' Voice - Commander Analysis

## Commander Strategy Overview
Atraxa is a powerhouse four-color commander (GWUB) that excels at incremental advantage through her proliferate ability. She creates value engines that compound over time, making her one of the most popular and versatile commanders in the format.

## Key Synergy Categories

### 1. Planeswalkers ("Superfriends")
- **Teferi, Hero of Dominaria** - Ultimate protection and card advantage
- **Jace, the Mind Sculptor** - Premium card selection and win condition
- **Elspeth, Sun's Champion** - Board presence and removal
- **Vraska the Unseen** - Removal and alternate win condition

### 2. +1/+1 Counter Strategies  
- **Doubling Season** - Doubles all counter effects
- **Hardened Scales** - Additional +1/+1 counters
- **Cathars' Crusade** - Team-wide counter distribution
- **Kalonian Hydra** - Exponential counter growth

### 3. Alternative Counter Types
- **Infect creatures** - Poison counters for alternate win
- **Energy cards** - Aether Hub, Glimmer of Genius
- **Experience counters** - Meren, Ezuri, Kalemne

## Specific Card Recommendations
1. **Doubling Season** - Core engine piece
2. **Deepglow Skate** - Instant proliferate on creatures
3. **Inexorable Tide** - Spell-based proliferate
4. **Contagion Engine** - Repeatable proliferate
5. **Viral Drake** - Flying proliferate creature
6. **Tezzeret's Gambit** - Card draw + proliferate
7. **Fuel for the Cause** - Counterspell + proliferate
8. **Gilder Bairn** - Untap proliferate
9. **Thrummingbird** - Evasive proliferate
10. **Steady Progress** - Scry + proliferate

## Win Conditions
- **Planeswalker Ultimates** - Protected by proliferate
- **Poison Damage** - Infect creatures + proliferate
- **Overwhelming Board State** - +1/+1 counter creatures
- **Value Engine Victory** - Out-resourcing opponents

## Mana Base Considerations
- **Four-color mana base** requires careful construction
- **Chromatic Lantern** - Color fixing essential
- **Command Tower** - Free four-color land
- **Exotic Orchard** - Usually produces all colors
- **Fetch lands + Shock lands** - Optimal but expensive
- **Vivid lands** - Budget four-color option

## Common Pitfalls
- **Over-reliance on commander** - Pack removal protection
- **Slow starts** - Include early game plays
- **Mana base issues** - Don't skimp on color fixing
- **Target priority** - Atraxa draws immediate attention
- **Counter dilution** - Focus on 2-3 counter types maximum
            """
        else:
            # Generic response for other commanders
            analysis = f"""
# {commander_name} - Commander Analysis

## Commander Strategy Overview
This commander offers unique strategic opportunities in the Commander format. The analysis would provide detailed insights into optimal deck construction, synergies, and win conditions.

## Key Synergy Categories
- Strategic card interactions
- Mana curve optimization  
- Win condition packages
- Meta considerations

## Specific Card Recommendations
[Detailed card recommendations would be provided here based on the commander's abilities and color identity]

## Win Conditions
[Primary and alternate win conditions for this commander]

## Mana Base Considerations
[Mana base requirements and recommendations]

## Common Pitfalls
[Things to avoid when building around this commander]

*Note: This is a mock response. Connect to Perplexity AI for detailed analysis.*
            """
        
        return {
            'commander': commander_name,
            'analysis': analysis.strip(),
            'citations': [
                "https://edhrec.com",
                "https://scryfall.com", 
                "https://mtg.fandom.com"
            ],
            'success': True,
            'mock': True
        }
    
    def analyze_card_synergies(self, target_cards: List[str], deck_theme: str) -> Dict[str, Any]:
        """Mock card synergy analysis."""
        return {
            'cards': target_cards,
            'theme': deck_theme,
            'analysis': f"Mock synergy analysis for {len(target_cards)} cards in a {deck_theme} themed deck.",
            'citations': ["https://edhrec.com"],
            'success': True,
            'mock': True
        }
    
    def suggest_budget_alternatives(self, expensive_cards: List[str], budget_limit: float) -> Dict[str, Any]:
        """Mock budget alternatives."""
        return {
            'original_cards': expensive_cards,
            'budget_limit': budget_limit,
            'alternatives': f"Mock budget alternatives under ${budget_limit} for {len(expensive_cards)} expensive cards.",
            'citations': ["https://edhrec.com"],
            'success': True,
            'mock': True
        }
    
    def analyze_meta_considerations(self, commander: str, playgroup_description: str = "casual") -> Dict[str, Any]:
        """Mock meta analysis."""
        return {
            'commander': commander,
            'playgroup': playgroup_description,
            'meta_analysis': f"Mock meta analysis for {commander} in {playgroup_description} playgroups.",
            'citations': ["https://edhrec.com"],
            'success': True,
            'mock': True
        }

def test_mock_client():
    """Test the mock client."""
    print("Testing Mock Perplexity Client...")
    print("(Using mock responses - API connection unavailable)")
    
    client = MockPerplexityClient()
    
    result = client.analyze_commander_synergies("Atraxa, Praetors' Voice")
    
    if result['success']:
        print("Mock client working!")
        print("\nMock Analysis Preview:")
        print(result['analysis'][:500] + "..." if len(result['analysis']) > 500 else result['analysis'])
        print(f"\nMock Sources: {len(result['citations'])} citations")
        if result.get('mock'):
            print("\nNote: This is a mock response for development purposes")
    else:
        print(f"Mock failed: {result['error']}")

if __name__ == "__main__":
    test_mock_client()