"""
Simple Perplexity client using requests (fallback for SDK issues)
"""
import os
import requests
import json
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class SimplePerplexityClient:
    """Simple Perplexity client using requests directly."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY must be set in environment or passed to constructor.")
        
        self.base_url = "https://api.perplexity.ai"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, messages: List[Dict[str, str]], model: str = "sonar-pro") -> Dict[str, Any]:
        """Make a request to the Perplexity API using requests."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1500,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error making request to Perplexity: {e}")
            raise

    def analyze_commander_synergies(self, commander_name: str, card_list: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze a commander and suggest synergistic cards and strategies."""
        deck_context = ""
        if card_list:
            deck_context = f"\n\nCurrent deck cards: {', '.join(card_list[:20])}" + \
                          ("..." if len(card_list) > 20 else "")
        
        messages = [{
            "role": "system",
            "content": """You are an expert Magic: The Gathering deck builder specializing in the Commander format. 
            Analyze commanders and provide strategic deck building advice focusing on:
            1. Card synergies and interactions
            2. Mana curve optimization
            3. Win conditions and game plans
            4. Meta considerations
            5. Budget alternatives when relevant
            
            Provide specific, actionable recommendations with clear reasoning."""
        }, {
            "role": "user",
            "content": f"""Analyze the MTG Commander "{commander_name}" for deck building. 
            Provide detailed analysis including:
            
            1. **Commander Strategy Overview**: What makes this commander effective?
            2. **Key Synergy Categories**: What types of cards work best with this commander?
            3. **Specific Card Recommendations**: Name 10-15 specific cards that synergize well
            4. **Win Conditions**: Primary ways this deck can win games
            5. **Mana Base Considerations**: Any special mana requirements or strategies
            6. **Common Pitfalls**: What to avoid when building around this commander
            
            Format your response as structured analysis with clear sections.{deck_context}"""
        }]
        
        try:
            response = self._make_request(messages)
            return {
                'commander': commander_name,
                'analysis': response['choices'][0]['message']['content'],
                'citations': response.get('citations', []),
                'success': True
            }
        except Exception as e:
            return {
                'commander': commander_name,
                'error': str(e),
                'success': False
            }

# Test function
def test_simple_client():
    """Test the simple client."""
    try:
        client = SimplePerplexityClient()
        
        print("Testing Simple Perplexity Client...")
        print("Analyzing Atraxa, Praetors' Voice...")
        
        result = client.analyze_commander_synergies("Atraxa, Praetors' Voice")
        
        if result['success']:
            print("Simple client working!")
            print("\nAnalysis Preview:")
            print(result['analysis'][:500] + "..." if len(result['analysis']) > 500 else result['analysis'])
            if result.get('citations'):
                print(f"\nSources: {len(result['citations'])} citations found")
        else:
            print(f"Analysis failed: {result['error']}")
            
    except Exception as e:
        print(f"Simple client test failed: {e}")

if __name__ == "__main__":
    test_simple_client()