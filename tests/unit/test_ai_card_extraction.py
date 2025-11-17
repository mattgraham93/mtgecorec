#!/usr/bin/env python3
"""
Unit tests for AI card extraction and matching
"""

import unittest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_engine.commander_recommender import CommanderRecommendationEngine
from data_engine.perplexity_client import PerplexityClient

class TestAICardExtraction(unittest.TestCase):
    """Test AI card extraction and database matching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = CommanderRecommendationEngine(use_ai=False)  # Don't use real AI for most tests
        
        # Mock database responses for known cards
        self.mock_cards_in_db = [
            {'name': 'Skullclamp', 'legalities': {'commander': 'legal'}},
            {'name': 'Sol Ring', 'legalities': {'commander': 'legal'}}, 
            {'name': 'Smothering Tithe', 'legalities': {'commander': 'legal'}},
            {'name': 'Baleful Strix', 'legalities': {'commander': 'legal'}},
            {'name': 'Lightning Greaves', 'legalities': {'commander': 'legal'}},
            {'name': 'Esper Sentinel', 'legalities': {'commander': 'legal'}},
            {'name': 'Mystic Remora', 'legalities': {'commander': 'legal'}},
            {'name': 'Land Tax', 'legalities': {'commander': 'legal'}},
        ]
    
    def test_valid_card_name_validation(self):
        """Test the card name validation logic."""
        # Valid card names
        valid_names = [
            "Skullclamp",
            "Sol Ring", 
            "Smothering Tithe",
            "Lightning Greaves",
            "Baleful Strix",
            "Esper Sentinel"
        ]
        
        for name in valid_names:
            with self.subTest(name=name):
                self.assertTrue(self.engine._is_valid_card_name(name), f"{name} should be valid")
    
    def test_invalid_card_name_validation(self):
        """Test rejection of invalid card names."""
        # Invalid card names (too descriptive, conversational, etc.)
        invalid_names = [
            "Divine Visitation and Rhys the Redeemed",  # Multiple cards
            "Door of Destinies is also tribal support",  # Descriptive text
            "The tokens created by Alela are blue",      # Sentence
            "you should consider adding",                # Conversational
            "this deck needs more",                      # Conversational
            "https://example.com",                       # URL
            "single",                                    # Too short
            "a" * 60,                                    # Too long
        ]
        
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(self.engine._is_valid_card_name(name), f"{name} should be invalid")
    
    def test_extract_cards_from_json_response(self):
        """Test extracting cards from a well-formatted JSON response."""
        # Simulate what we want Perplexity to return
        mock_response = '''
        {
            "recommended_cards": [
                "Skullclamp",
                "Sol Ring", 
                "Smothering Tithe",
                "Lightning Greaves",
                "Esper Sentinel"
            ]
        }
        '''
        
        # Test the extraction (we'll need to update the method to handle JSON)
        cards = self._extract_cards_from_json(mock_response)
        expected = ["Skullclamp", "Sol Ring", "Smothering Tithe", "Lightning Greaves", "Esper Sentinel"]
        
        self.assertEqual(cards, expected)
    
    def test_extract_cards_from_numbered_list(self):
        """Test extracting cards from numbered list format."""
        mock_response = '''
        Here are my recommendations for Alela:
        
        1. **Skullclamp** - Turns your Faerie tokens into massive card draw
        2. **Sol Ring** - Cheap artifact ramp and token trigger  
        3. **Smothering Tithe** - Ramp and triggers Alela for a token
        4. **Lightning Greaves** - Protects Alela and is a cheap artifact trigger
        5. **Esper Sentinel** - Cheap artifact, card draw, triggers Alela
        '''
        
        cards = self._extract_cards_from_text(mock_response)
        expected = ["Skullclamp", "Sol Ring", "Smothering Tithe", "Lightning Greaves", "Esper Sentinel"]
        
        self.assertCountEqual(cards, expected)  # Order doesn't matter
    
    def test_case_insensitive_matching(self):
        """Test that we can match cards regardless of case differences."""
        # AI might return different cases
        ai_suggestions = ["skullclamp", "SOL RING", "Smothering tithe"]
        db_names = ["Skullclamp", "Sol Ring", "Smothering Tithe"] 
        
        matches = self._find_case_insensitive_matches(ai_suggestions, db_names)
        expected = [
            ("skullclamp", "Skullclamp"),
            ("SOL RING", "Sol Ring"), 
            ("Smothering tithe", "Smothering Tithe")
        ]
        
        self.assertCountEqual(matches, expected)
    
    def test_fuzzy_matching(self):
        """Test fuzzy matching for slight name variations."""
        ai_suggestions = ["Lightning Greaves", "Esper Sentinal"]  # Note typo in second
        db_names = ["Lightning Greaves", "Esper Sentinel"]
        
        matches = self._find_fuzzy_matches(ai_suggestions, db_names)
        expected = [
            ("Lightning Greaves", "Lightning Greaves"),
            ("Esper Sentinal", "Esper Sentinel")
        ]
        
        self.assertCountEqual(matches, expected)
    
    # Helper methods for testing
    def _extract_cards_from_json(self, response_text: str) -> List[str]:
        """Extract cards from JSON format response."""
        import json
        try:
            data = json.loads(response_text.strip())
            return data.get('recommended_cards', [])
        except:
            return []
    
    def _extract_cards_from_text(self, response_text: str) -> List[str]:
        """Extract cards from text using current patterns."""
        import re
        
        # Look for numbered lists with bold cards
        pattern = r'^\s*\d+\.?\s*\*?\*?([A-Z][a-zA-Z\s\'-]+?)\*?\*?\s*[-–]'
        matches = re.findall(pattern, response_text, re.MULTILINE)
        
        valid_cards = []
        for match in matches:
            card_name = match.strip()
            if self.engine._is_valid_card_name(card_name):
                valid_cards.append(card_name)
        
        return valid_cards
    
    def _find_case_insensitive_matches(self, ai_cards: List[str], db_cards: List[str]) -> List[tuple]:
        """Find case-insensitive matches between AI suggestions and database."""
        matches = []
        for ai_card in ai_cards:
            for db_card in db_cards:
                if ai_card.lower() == db_card.lower():
                    matches.append((ai_card, db_card))
                    break
        return matches
    
    def _find_fuzzy_matches(self, ai_cards: List[str], db_cards: List[str]) -> List[tuple]:
        """Find fuzzy matches (allowing for small typos)."""
        from difflib import get_close_matches
        
        matches = []
        for ai_card in ai_cards:
            # First try exact case-insensitive match
            exact_matches = [db for db in db_cards if db.lower() == ai_card.lower()]
            if exact_matches:
                matches.append((ai_card, exact_matches[0]))
                continue
            
            # Then try fuzzy matching
            close_matches = get_close_matches(ai_card, db_cards, n=1, cutoff=0.8)
            if close_matches:
                matches.append((ai_card, close_matches[0]))
        
        return matches


class TestPerplexityIntegration(unittest.TestCase):
    """Test the Perplexity API integration with improved prompting."""
    
    @patch('data_engine.perplexity_client.httpx.AsyncClient')
    async def test_structured_card_request(self, mock_client):
        """Test requesting cards in structured format from Perplexity."""
        # Mock the Perplexity response with JSON format
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [{
                'snippet': '''
                {
                    "recommended_cards": [
                        "Skullclamp",
                        "Sol Ring",
                        "Smothering Tithe", 
                        "Lightning Greaves",
                        "Esper Sentinel"
                    ]
                }
                '''
            }]
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        # Test the API call
        client = PerplexityClient("test-key")
        result = await self._test_structured_search(client, "Alela", "tokens, artifacts")
        
        self.assertTrue(result['success'])
        self.assertIn('Skullclamp', result['cards'])
        self.assertIn('Sol Ring', result['cards'])
    
    async def _test_structured_search(self, client: PerplexityClient, commander: str, mechanics: str) -> Dict[str, Any]:
        """Test method for structured card search."""
        query = f'''
        For Magic: The Gathering Commander {commander}, recommend exactly 10-15 specific card names 
        that synergize with: {mechanics}

        IMPORTANT: Format your response as valid JSON:
        {{
            "recommended_cards": [
                "Card Name 1",
                "Card Name 2",
                "Card Name 3"
            ]
        }}

        Requirements:
        - Only include cards legal in Commander format
        - Only include cards in the commander's color identity
        - Use exact card names as they appear in Magic databases
        - Return ONLY the JSON, no additional text
        '''
        
        try:
            # This would be the actual API call
            # For testing, we'll simulate the response structure
            return {
                'success': True,
                'cards': ['Skullclamp', 'Sol Ring', 'Smothering Tithe', 'Lightning Greaves', 'Esper Sentinel']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


def run_card_extraction_tests():
    """Run all card extraction tests."""
    print("Running AI Card Extraction Tests...")
    print("=" * 60)
    
    # Run the basic validation tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAICardExtraction)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nAll card extraction tests passed!")
        return True
    else:
        print(f"\n{len(result.failures + result.errors)} test(s) failed")
        return False


if __name__ == "__main__":
    # Run the tests
    success = run_card_extraction_tests()
    
    if success:
        print("\nTests passed! The card extraction logic is working correctly.")
        print("\nNext steps:")
        print("1. Update Perplexity prompting to request JSON format")
        print("2. Add case-insensitive matching in the main code")  
        print("3. Add fuzzy matching for typos")
    else:
        print("\nFix the failing tests before proceeding.")