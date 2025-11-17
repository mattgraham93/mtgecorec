"""
commander_recommender.py - Core Commander deck recommendation engine

This module provides the main recommendation system for Commander deck building,
combining synergy analysis, AI insights, and strategic deck building principles.
"""
import sys
import os
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
import random
from collections import defaultdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine.cosmos_driver import get_mongo_client, get_collection
from data_engine.commander_model import CommanderCard, CommanderDeck, CommanderAnalyzer, CommanderArchetype, ColorIdentity
from data_engine.synergy_analyzer import SynergyAnalyzer, SynergyScore
from data_engine.perplexity_client import PerplexityClient


@dataclass
class RecommendationRequest:
    """Request for deck recommendations."""
    commander_name: str
    current_deck: List[str] = None  # Card names already in deck
    budget_limit: Optional[float] = None  # Per card budget in USD
    archetype_preference: Optional[CommanderArchetype] = None
    power_level: str = "casual"  # casual, competitive, cedh
    include_combos: bool = True
    exclude_cards: List[str] = None  # Cards to avoid
    meta_focus: str = "multiplayer"  # multiplayer, 1v1


@dataclass
class CardRecommendation:
    """A single card recommendation with reasoning."""
    card_name: str
    card_data: Dict[str, Any]
    confidence_score: float  # 0.0 to 1.0
    synergy_score: float
    reasons: List[str]
    category: str  # 'ramp', 'removal', 'draw', 'synergy', 'combo', 'finisher'
    estimated_price: Optional[float] = None


@dataclass
class DeckRecommendation:
    """Complete deck building recommendations."""
    commander: CommanderCard
    recommendations: List[CardRecommendation]
    ai_analysis: Optional[Dict[str, Any]] = None
    mana_base_suggestions: List[CardRecommendation] = None
    deck_strategy: str = ""
    power_level_assessment: str = ""
    estimated_total_cost: Optional[float] = None


class CommanderRecommendationEngine:
    """Main engine for generating Commander deck recommendations."""
    
    def __init__(self, use_ai: bool = True):
        self.synergy_analyzer = SynergyAnalyzer()
        self.commander_analyzer = CommanderAnalyzer()
        self.use_ai = use_ai
        
        if use_ai:
            try:
                self.ai_client = PerplexityClient()
            except ValueError:
                print("Warning: Perplexity API key not found. AI analysis disabled.")
                self.use_ai = False
        
        # Card categories for balanced deck building
        self.deck_categories = {
            'ramp': ['ramp', 'mana', 'land', 'accelerate'],
            'removal': ['destroy', 'exile', 'counter', 'bounce'],
            'draw': ['draw', 'card advantage'],
            'protection': ['hexproof', 'indestructible', 'protection'],
            'finishers': ['win condition', 'damage', 'alternate win'],
            'utility': ['tutor', 'search', 'versatile'],
            'synergy': ['commander synergy', 'theme support']
        }
        
        # Recommended card counts by category
        self.category_targets = {
            'lands': 37,
            'ramp': 10,
            'removal': 8,
            'draw': 10,
            'protection': 3,
            'finishers': 5,
            'utility': 5,
            'synergy': 22  # Remaining slots
        }
    
    def get_card_database(self) -> List[Dict[str, Any]]:
        """Get all cards from the database."""
        try:
            client = get_mongo_client()
            collection = get_collection(client, 'mtgecorec', 'cards')
            
            # Filter for Commander-legal cards
            query = {
                'legalities.commander': {'$in': ['legal', 'restricted']},
                'type_line': {'$exists': True}
            }
            
            cards = list(collection.find(query, {
                'name': 1, 'mana_cost': 1, 'cmc': 1, 'colors': 1,
                'type_line': 1, 'oracle_text': 1, 'power': 1, 'toughness': 1,
                'rarity': 1, 'set': 1, 'legalities': 1, 'price': 1,
                '_id': 0
            }).limit(50000))  # Reasonable limit for performance
            
            return cards
        except Exception as e:
            print(f"Error accessing card database: {e}")
            return []
    
    def find_commander_cards(self, commander_name: str) -> List[CommanderCard]:
        """Find potential commander cards by name."""
        try:
            client = get_mongo_client()
            collection = get_collection(client, 'mtgecorec', 'cards')
            
            # Search for commander by name (fuzzy match)
            query = {
                'name': {'$regex': commander_name, '$options': 'i'},
                '$or': [
                    {'type_line': {'$regex': 'Legendary.*Creature', '$options': 'i'}},
                    {'type_line': {'$regex': 'Legendary.*Planeswalker', '$options': 'i'}},
                    {'oracle_text': {'$regex': 'can be your commander', '$options': 'i'}}
                ]
            }
            
            cards_data = list(collection.find(query))
            commanders = []
            
            for card_data in cards_data:
                try:
                    commander = CommanderCard.from_card_data(card_data)
                    if commander.can_be_commander:
                        commanders.append(commander)
                except Exception as e:
                    print(f"Error processing commander {card_data.get('name')}: {e}")
            
            return commanders
        except Exception as e:
            print(f"Error finding commanders: {e}")
            return []
    
    def categorize_card(self, card: Dict[str, Any]) -> str:
        """Determine the primary category of a card."""
        oracle_text = card.get('oracle_text', '').lower()
        type_line = card.get('type_line', '').lower()
        cmc = card.get('cmc', 0)
        
        # Land
        if 'land' in type_line:
            return 'lands'
        
        # Ramp
        if any(keyword in oracle_text for keyword in ['search your library for a land', 'add mana', 'mana cost', 'sol ring']):
            return 'ramp'
        
        # Removal
        if any(keyword in oracle_text for keyword in ['destroy target', 'exile target', 'counter target spell', 'return target']):
            return 'removal'
        
        # Card draw
        if any(keyword in oracle_text for keyword in ['draw cards', 'draw a card', 'card draw']):
            return 'draw'
        
        # Protection
        if any(keyword in oracle_text for keyword in ['hexproof', 'indestructible', 'protection from', 'ward']):
            return 'protection'
        
        # Finishers (high impact cards)
        if (cmc >= 6 or 'win the game' in oracle_text or 
            any(keyword in oracle_text for keyword in ['each opponent loses', 'deal damage to each opponent'])):
            return 'finishers'
        
        # Utility (tutors, versatile spells)
        if any(keyword in oracle_text for keyword in ['search your library', 'choose one', 'modal']):
            return 'utility'
        
        # Default to synergy
        return 'synergy'
    
    def filter_cards_by_identity(self, cards: List[Dict[str, Any]], commander_identity: ColorIdentity) -> List[Dict[str, Any]]:
        """Filter cards that are legal in the commander's color identity."""
        legal_cards = []
        
        for card in cards:
            # Skip basic lands and commanders themselves
            if ('Basic' in card.get('type_line', '') and 'Land' in card.get('type_line', '')):
                continue
            if 'Legendary' in card.get('type_line', '') and 'Creature' in card.get('type_line', ''):
                continue
                
            # Check color identity
            card_identity = ColorIdentity.from_mana_cost_and_rules_text(
                card.get('mana_cost', ''), card.get('oracle_text', '')
            )
            
            if commander_identity.contains(card_identity):
                legal_cards.append(card)
        
        return legal_cards
    
    def score_card_for_commander(self, commander: CommanderCard, card: Dict[str, Any], 
                                current_deck: List[str] = None) -> CardRecommendation:
        """Score a single card for inclusion in the commander deck."""
        card_name = card.get('name', '')
        
        # Calculate synergy with commander
        synergy = self.synergy_analyzer.calculate_commander_synergy(commander, card)
        
        # Base confidence from synergy
        confidence = synergy.score
        
        # Adjust for card quality indicators
        cmc = card.get('cmc', 0)
        rarity = card.get('rarity', 'common')
        
        # Lower CMC generally better (with exceptions)
        if cmc <= 3:
            confidence += 0.1
        elif cmc >= 7:
            confidence -= 0.1
        
        # Rarity bonus (higher rarity often means more powerful)
        rarity_bonus = {
            'mythic': 0.15,
            'rare': 0.1,
            'uncommon': 0.05,
            'common': 0.0
        }
        confidence += rarity_bonus.get(rarity, 0.0)
        
        # Check if card fits deck strategy
        category = self.categorize_card(card)
        
        # Penalty for duplicate effects (if we have current deck)
        if current_deck:
            similar_effects = sum(1 for existing_card in current_deck 
                                if self.categorize_card({'oracle_text': existing_card}) == category)
            if similar_effects > 3:  # Too many of same type
                confidence -= 0.2
        
        # Estimate price
        estimated_price = card.get('price', 0.0) if card.get('price') else None
        
        return CardRecommendation(
            card_name=card_name,
            card_data=card,
            confidence_score=min(confidence, 1.0),
            synergy_score=synergy.score,
            reasons=synergy.reasons + [f"Category: {category}"],
            category=category,
            estimated_price=estimated_price
        )
    
    def generate_mana_base(self, commander: CommanderCard, budget_limit: Optional[float] = None) -> List[CardRecommendation]:
        """Generate mana base recommendations for the commander."""
        colors = commander.color_identity.colors
        color_count = len(colors)
        
        mana_base = []
        
        # Basic lands (free)
        if colors:
            basic_lands = {
                'W': 'Plains',
                'U': 'Island', 
                'B': 'Swamp',
                'R': 'Mountain',
                'G': 'Forest'
            }
            
            # Distribute basics evenly
            basics_per_color = max(3, 12 // color_count) if color_count > 0 else 0
            
            for color in colors:
                if color in basic_lands:
                    mana_base.append(CardRecommendation(
                        card_name=basic_lands[color],
                        card_data={'name': basic_lands[color], 'type_line': 'Basic Land', 'oracle_text': f'{{T}}: Add {{{color}}}.'},
                        confidence_score=1.0,
                        synergy_score=0.8,
                        reasons=[f"Basic {color} mana source"],
                        category='lands',
                        estimated_price=0.1
                    ))
        
        # Add colorless utility lands
        utility_lands = [
            ('Command Tower', 1.0, ["Perfect mana fixing for commanders"]),
            ('Sol Ring', 1.0, ["Essential mana acceleration"]),
            ('Arcane Signet', 0.9, ["Excellent mana rock"]),
        ]
        
        for land_name, confidence, reasons in utility_lands:
            if not budget_limit or budget_limit > 5.0:  # Assume these are reasonably priced
                mana_base.append(CardRecommendation(
                    card_name=land_name,
                    card_data={'name': land_name, 'type_line': 'Artifact' if 'Ring' in land_name or 'Signet' in land_name else 'Land'},
                    confidence_score=confidence,
                    synergy_score=0.7,
                    reasons=reasons,
                    category='ramp' if 'Ring' in land_name or 'Signet' in land_name else 'lands',
                    estimated_price=2.0
                ))
        
        return mana_base
    
    async def generate_recommendations(self, request: RecommendationRequest) -> DeckRecommendation:
        """Generate complete deck recommendations based on request."""
        # Find the commander
        commanders = self.find_commander_cards(request.commander_name)
        if not commanders:
            raise ValueError(f"Commander '{request.commander_name}' not found")
        
        commander = commanders[0]  # Use first match
        
        # Get AI analysis if available
        ai_analysis = None
        if self.use_ai:
            try:
                current_cards = request.current_deck or []
                ai_result = self.ai_client.analyze_commander_synergies(commander.name, current_cards)
                if ai_result['success']:
                    ai_analysis = ai_result
            except Exception as e:
                print(f"AI analysis failed: {e}")
        
        # Get all legal cards for this commander
        print("Loading card database...")
        all_cards = self.get_card_database()
        legal_cards = self.filter_cards_by_identity(all_cards, commander.color_identity)
        
        print(f"Found {len(legal_cards)} legal cards for {commander.name}")
        
        # Score all cards
        print("Scoring cards...")
        scored_cards = []
        for card in legal_cards:
            # Skip cards in exclude list
            if request.exclude_cards and card.get('name') in request.exclude_cards:
                continue
            
            # Skip expensive cards if budget limited
            if request.budget_limit and card.get('price', 0) > request.budget_limit:
                continue
            
            recommendation = self.score_card_for_commander(commander, card, request.current_deck)
            scored_cards.append(recommendation)
        
        # Sort by confidence score
        scored_cards.sort(key=lambda x: x.confidence_score, reverse=True)
        
        # Balance recommendations by category
        category_counts = defaultdict(int)
        balanced_recommendations = []
        
        for rec in scored_cards:
            category = rec.category
            target_count = self.category_targets.get(category, 5)
            
            if category_counts[category] < target_count:
                balanced_recommendations.append(rec)
                category_counts[category] += 1
            
            # Stop when we have enough cards
            if len(balanced_recommendations) >= 63:  # 100 - 37 lands
                break
        
        # Generate mana base
        mana_base = self.generate_mana_base(commander, request.budget_limit)
        
        # Calculate total estimated cost
        total_cost = None
        if request.budget_limit:
            card_costs = [rec.estimated_price for rec in balanced_recommendations if rec.estimated_price]
            mana_costs = [rec.estimated_price for rec in mana_base if rec.estimated_price]
            if card_costs or mana_costs:
                total_cost = sum(card_costs + mana_costs)
        
        # Determine power level
        avg_confidence = sum(rec.confidence_score for rec in balanced_recommendations) / len(balanced_recommendations) if balanced_recommendations else 0
        if avg_confidence > 0.7:
            power_assessment = "High - Competitive focused"
        elif avg_confidence > 0.4:
            power_assessment = "Medium - Optimized casual"
        else:
            power_assessment = "Low - Casual battlecruiser"
        
        return DeckRecommendation(
            commander=commander,
            recommendations=balanced_recommendations,
            ai_analysis=ai_analysis,
            mana_base_suggestions=mana_base,
            deck_strategy=f"This deck focuses on {commander.name}'s abilities and synergistic interactions.",
            power_level_assessment=power_assessment,
            estimated_total_cost=total_cost
        )


async def test_recommendation_engine():
    """Test the recommendation engine with a sample request."""
    print("Testing Commander Recommendation Engine...")
    
    engine = CommanderRecommendationEngine(use_ai=False)  # Disable AI for testing
    
    request = RecommendationRequest(
        commander_name="Atraxa",
        budget_limit=10.0,
        power_level="casual"
    )
    
    try:
        recommendations = await engine.generate_recommendations(request)
        
        print(f"\n✅ Generated recommendations for {recommendations.commander.name}")
        print(f"Color Identity: {recommendations.commander.color_identity.to_string()}")
        print(f"Power Level: {recommendations.power_level_assessment}")
        
        print(f"\nTop 10 Card Recommendations:")
        for i, rec in enumerate(recommendations.recommendations[:10], 1):
            print(f"{i}. {rec.card_name} (Confidence: {rec.confidence_score:.2f}, Category: {rec.category})")
            if rec.reasons:
                print(f"   Reason: {rec.reasons[0]}")
        
        print(f"\nMana Base ({len(recommendations.mana_base_suggestions)} cards):")
        for rec in recommendations.mana_base_suggestions[:5]:
            print(f"- {rec.card_name}")
        
        if recommendations.estimated_total_cost:
            print(f"\nEstimated Total Cost: ${recommendations.estimated_total_cost:.2f}")
        
        print("✅ Recommendation engine test complete!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_recommendation_engine())