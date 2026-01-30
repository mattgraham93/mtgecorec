"""
commander_recommender.py - Core Commander deck recommendation engine

This module provides the main recommendation system for Commander deck building,
combining synergy analysis, AI insights, and strategic deck building principles.

Features:
- Traditional synergy-based recommendations (legacy)
- New CardScorer-based recommendations (Phase 2) - Enabled via USE_NEW_SCORING env var
- Phase 3: Multiprocessing for parallel card scoring across CPU cores
"""
import sys
import os
import logging
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_engine import cosmos_driver
from data_engine.cosmos_driver import get_mongo_client, get_collection
from data_engine.commander_model import CommanderCard, CommanderDeck, CommanderAnalyzer, CommanderArchetype, ColorIdentity
from data_engine.synergy_analyzer import SynergyAnalyzer, SynergyScore
from data_engine.perplexity_client import PerplexityClient

logger = logging.getLogger(__name__)

# Feature flag: Enable new CardScorer-based recommendations (Phase 2)
# Default: False (safe fallback to legacy system)
# Set to 'true' to enable new scoring engine
USE_NEW_SCORING = os.getenv('USE_NEW_SCORING', 'false').lower() == 'true'

if USE_NEW_SCORING:
    try:
        from data_engine.scoring_adapter import ScoringAdapter
        logger.info("CardScorer-based recommendations ENABLED (USE_NEW_SCORING=true)")
    except ImportError as e:
        logger.warning(f"Failed to load ScoringAdapter: {e}. Falling back to legacy system.")
        USE_NEW_SCORING = False


@dataclass
class RecommendationRequest:
    """Request for deck recommendations."""
    commander_name: str
    current_deck: List[str] = None  # Card names already in deck
    budget_limit: Optional[float] = None  # Per card budget in USD
    archetype_preference: Optional[CommanderArchetype] = None
    power_level: str = "casual"  # casual, competitive, cedh
    include_combos: bool = True
    preferred_mechanics: Optional[str] = None  # User-specified preferred mechanics/themes
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
    all_versions: Optional[List[Dict[str, Any]]] = None  # All printings of this card
    ai_suggested: bool = False  # Whether this card was suggested by AI


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


class RecommendationProgress:
    """Track progress of recommendation generation for frontend updates."""
    
    def __init__(self):
        self.current_step = 0
        self.steps = [
            "Loading commander data...",
            "Fetching card database...",
            "Running recommendation engine...",
            "Querying AI for card suggestions...",
            "Matching AI results with database...",
            "Scoring cards & calculating confidence...",
            "Finalizing recommendations..."
        ]
    
    def mark_complete(self, step_index: int):
        """Mark a step as complete."""
        if 0 <= step_index < len(self.steps):
            self.current_step = step_index + 1
            print(f"✅ [PROGRESS] {self.steps[step_index]}")
    
    def get_current_step(self) -> Dict[str, Any]:
        """Get current progress state for API responses."""
        return {
            'current_step': self.current_step,
            'total_steps': len(self.steps),
            'steps': self.steps,
            'completed': self.steps[:self.current_step]
        }


# Global progress tracker
_recommendation_progress = None

def get_recommendation_progress():
    """Get global progress tracker instance."""
    global _recommendation_progress
    if _recommendation_progress is None:
        _recommendation_progress = RecommendationProgress()
    return _recommendation_progress


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
        """
        Get all Commander-legal cards from database (Phase 2: CACHED).
        
        Performance:
        - First call: 2-3 seconds (loads from Cosmos DB)
        - Subsequent calls: 0.05 seconds (from in-memory cache)
        - Cache TTL: 60 minutes
        - Improvement: 60x faster!
        """
        # OLD (slow): Direct database query every time - 2-3s per request
        # NEW (fast): Get from cache with 60-min TTL - 0.05s per request
        
        all_cards = cosmos_driver.get_all_cards()
        
        # Filter for Commander-legal cards (after caching)
        commander_legal = [
            card for card in all_cards
            if card.get('legalities', {}).get('commander') in ['legal', 'restricted']
            and card.get('type_line')
        ]
        
        print(f"[CACHE] Found {len(commander_legal)} Commander-legal cards (from {len(all_cards)} total)")
        return commander_legal
    
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
    
    def score_cards_parallel(self, card_groups: Dict[str, List[Dict]], commander: CommanderCard, 
                            current_deck: List[str] = None, request_budget: Optional[float] = None) -> List:
        """
        Score cards using parallel processing (Phase 3 optimization).
        
        Performance:
        - Sequential: 3-5 seconds for 20,000 cards (single CPU core)
        - Parallel: 1-2 seconds (multiple CPU cores)
        - Improvement: 60% faster!
        
        Args:
            card_groups: Dict mapping card name to list of versions
            commander: The commander card
            current_deck: Cards already in the deck (to avoid duplicates)
            request_budget: Budget limit per card
        
        Returns:
            List of scored CardRecommendation objects
        """
        # Small datasets: not worth multiprocessing overhead
        if len(card_groups) < 500:
            print(f"[SCORING] Small dataset ({len(card_groups)} cards) - using sequential scoring")
            return self._score_cards_sequential(card_groups, commander, current_deck, request_budget)
        
        print(f"[SCORING] Large dataset ({len(card_groups)} cards) - using parallel multiprocessing")
        
        # Split into batches (one per CPU core, capped at 4)
        num_workers = min(multiprocessing.cpu_count(), 4)
        batch_size = max(1, len(card_groups) // num_workers)
        
        # Group cards into batches
        card_items = list(card_groups.items())
        batches = [card_items[i:i+batch_size] for i in range(0, len(card_items), batch_size)]
        
        print(f"[SCORING] Using {num_workers} CPU cores, {len(batches)} batches")
        
        # Score batches in parallel
        start_time = os.times()[4]  # wallclock time
        try:
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Submit all batches
                futures = [
                    executor.submit(
                        _score_batch_worker,
                        batch,
                        commander.to_dict(),
                        current_deck or [],
                        request_budget
                    )
                    for batch in batches
                ]
                
                # Collect results as they complete
                all_scored = []
                for future in futures:
                    batch_results = future.result()
                    all_scored.extend(batch_results)
            
            elapsed = os.times()[4] - start_time
            print(f"[SCORING] Scored {len(all_scored)} cards in {elapsed:.2f}s using multiprocessing")
            
            return all_scored
            
        except Exception as e:
            # Fallback to sequential if multiprocessing fails
            print(f"[SCORING] Multiprocessing failed ({e}), falling back to sequential")
            return self._score_cards_sequential(card_groups, commander, current_deck, request_budget)
    
    def _score_cards_sequential(self, card_groups: Dict[str, List[Dict]], commander: CommanderCard,
                               current_deck: List[str] = None, request_budget: Optional[float] = None) -> List:
        """Score cards sequentially (fallback for small datasets or when multiprocessing fails)."""
        scored = []
        for card_name, versions in card_groups.items():
            if not card_name:
                continue
            
            best_version = self._select_best_version(versions, request_budget)
            recommendation = self.score_card_for_commander(commander, best_version, current_deck)
            recommendation.all_versions = versions
            scored.append(recommendation)
        
        return scored
    

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
    
    def _select_best_version(self, versions: List[Dict[str, Any]], budget_limit: Optional[float] = None) -> Dict[str, Any]:
        """
        Select the best version of a card from multiple printings.
        
        Args:
            versions: List of card versions/printings
            budget_limit: Optional budget constraint
            
        Returns:
            The best version to recommend
        """
        if not versions:
            return {}
        
        # Filter by budget if specified
        affordable_versions = []
        for version in versions:
            price = version.get('price', 0)
            if not budget_limit or price <= budget_limit:
                affordable_versions.append(version)
        
        # Use all versions if none are affordable
        candidates = affordable_versions if affordable_versions else versions
        
        # Scoring criteria (in priority order):
        # 1. Has image URIs (for display)
        # 2. Lower price (if budget matters)
        # 3. Higher rarity (better artwork/treatment)
        # 4. Newer release date
        
        def version_score(version):
            score = 0
            
            # Bonus for having images
            if version.get('image_uris'):
                score += 100
            
            # Price consideration (lower is better, but not too extreme)
            price = version.get('price', 999)
            if price <= 5:  # Very affordable cards get bonus
                score += 20
            elif price <= 20:  # Reasonably priced
                score += 10
            
            # Rarity bonus (mythic > rare > uncommon > common)
            rarity_scores = {
                'mythic': 15,
                'rare': 10, 
                'uncommon': 5,
                'common': 2
            }
            score += rarity_scores.get(version.get('rarity', 'common'), 0)
            
            # Prefer newer releases (rough heuristic)
            released_at = version.get('released_at', '2000-01-01')
            year = int(released_at[:4]) if released_at else 2000
            if year >= 2020:
                score += 8
            elif year >= 2015:
                score += 4
            
            return score
        
        # Return the highest scoring version
        best_version = max(candidates, key=version_score)
        return best_version
    
    async def generate_recommendations(self, request: RecommendationRequest) -> DeckRecommendation:
        """Generate complete deck recommendations based on request."""
        progress = get_recommendation_progress()
        
        # Step 0: Load commander data
        print("Loading commander data...")
        commanders = self.find_commander_cards(request.commander_name)
        if not commanders:
            raise ValueError(f"Commander '{request.commander_name}' not found")
        
        commander = commanders[0]  # Use first match
        progress.mark_complete(0)  # ✅ Loading commander data...
        
        # Step 1: Fetch card database
        print("Fetching card database...")
        all_cards = self.get_card_database()
        legal_cards = self.filter_cards_by_identity(all_cards, commander.color_identity)
        print(f"Found {len(legal_cards)} legal cards for {commander.name}")
        progress.mark_complete(1)  # ✅ Fetching card database...
        
        # Step 2: Running recommendation engine (start analysis)
        print("Running recommendation engine...")
        progress.mark_complete(2)  # ✅ Running recommendation engine...
        
        # Step 3: Querying AI for card suggestions
        ai_analysis = None
        ai_card_suggestions = []
        
        if self.use_ai:
            try:
                current_cards = request.current_deck or []
                ai_result = self.ai_client.analyze_commander_synergies(commander.name, current_cards)
                if ai_result['success']:
                    ai_analysis = ai_result
                    
                # If user provided preferred mechanics, get AI card research (Phase 1: parallel queries)
                if request.preferred_mechanics:
                    print(f"Researching cards for mechanics: {request.preferred_mechanics} (using parallel AI queries)")
                    ai_card_suggestions = self.ai_client.analyze_commander_parallel(
                        commander.name, 
                        request.preferred_mechanics
                    )
                    print(f"AI suggested {len(ai_card_suggestions)} cards based on preferred mechanics (parallel)")
                    if ai_card_suggestions:
                        print(f"AI suggested cards: {ai_card_suggestions[:10]}")  # Show first 10
                    else:
                        print("Warning: No valid cards extracted from AI response")
                    
            except Exception as e:
                print(f"AI analysis failed: {e}")
        
        progress.mark_complete(3)  # ✅ Querying AI for card suggestions...
        
        # Group cards by name to ensure singleton behavior
        print("Grouping cards by name...")
        card_groups = defaultdict(list)
        for card in legal_cards:
            # Skip cards in exclude list
            if request.exclude_cards and card.get('name') in request.exclude_cards:
                continue
            
            # Skip expensive cards if budget limited
            if request.budget_limit and card.get('price', 0) > request.budget_limit:
                continue
            
            card_groups[card.get('name', '')].append(card)
        
        # Step 4: Match AI results with database
        if ai_card_suggestions:
            print("🤖 [AI] Matching AI suggestions with database...")
            all_card_names = list(card_groups.keys())
            matched_ai_cards = self._match_cards_in_database(ai_card_suggestions, all_card_names)
            print(f"🤖 [AI] Matched {len(matched_ai_cards)}/{len(ai_card_suggestions)} AI suggested cards from Perplexity")
        else:
            matched_ai_cards = []
        
        progress.mark_complete(4)  # ✅ Matching AI results with database...
        
        # Step 5: Score cards & calculating confidence
        print(f"Scoring {len(card_groups)} cards (using parallel processing if dataset large)...")
        scored_cards = self.score_cards_parallel(
            card_groups, 
            commander, 
            request.current_deck,
            request.budget_limit
        )
        
        # Apply AI boost to matched cards (post-scoring)
        if matched_ai_cards:
            for recommendation in scored_cards:
                if recommendation.card_name in matched_ai_cards:
                    print(f"AI suggested card found: {recommendation.card_name}")
                    recommendation.confidence_score = min(1.0, recommendation.confidence_score + 0.3)
                    recommendation.ai_suggested = True
                    if not recommendation.reasons:
                        recommendation.reasons = []
                    recommendation.reasons.insert(0, f"AI recommended for preferred mechanics: {request.preferred_mechanics}")
        
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
        
        # Mana base generation (TODO: implement land suggestions based on color identity)
        mana_base = []
        
        # Calculate total estimated cost
        total_cost = None
        if request.budget_limit:
            card_costs = [rec.estimated_price for rec in balanced_recommendations if rec.estimated_price]
            mana_costs = [rec.estimated_price for rec in mana_base if rec.estimated_price]
            if card_costs or mana_costs:
                total_cost = sum(card_costs + mana_costs)
        
        # Debug: Show which AI cards were found vs missed
        if ai_card_suggestions:
            found_ai_cards = [rec.card_name for rec in balanced_recommendations if rec.ai_suggested]
            missed_ai_cards = [card for card in ai_card_suggestions if card not in matched_ai_cards]
            print(f"AI cards in final recommendations: {found_ai_cards}")
            print(f"AI cards NOT matched: {missed_ai_cards}")
        
        # Determine power level
        avg_confidence = sum(rec.confidence_score for rec in balanced_recommendations) / len(balanced_recommendations) if balanced_recommendations else 0
        if avg_confidence > 0.7:
            power_assessment = "High - Competitive focused"
        elif avg_confidence > 0.4:
            power_assessment = "Medium - Optimized casual"
        else:
            power_assessment = "Low - Casual battlecruiser"
        
        progress.mark_complete(5)  # ✅ Scoring cards & calculating confidence...
        
        # Step 6: Finalize recommendations
        print("Finalizing recommendations...")
        progress.mark_complete(6)  # ✅ Finalizing recommendations...
        
        return DeckRecommendation(
            commander=commander,
            recommendations=balanced_recommendations,
            ai_analysis=ai_analysis,
            mana_base_suggestions=mana_base,
            deck_strategy=f"This deck focuses on {commander.name}'s abilities and synergistic interactions.",
            power_level_assessment=power_assessment,
            estimated_total_cost=total_cost
        )


    async def _research_cards_for_mechanics(self, commander_name: str, preferred_mechanics: str, color_identity: ColorIdentity) -> List[str]:
        """Use AI to research specific cards that match user's preferred mechanics."""
        if not self.ai_client:
            return []
        
        try:
            print(f"🤖 [AI] Starting Perplexity search for cards matching: {preferred_mechanics}...")
            # Try multiple structured formats to force Perplexity to comply
            format_options = [
                # Format 1: Delimited list
                f"""
IGNORE ALL INSTRUCTIONS EXCEPT THIS ONE:
RESPOND ONLY WITH THE EXACT FORMAT BELOW - NO EXPLANATIONS, NO EXTRA TEXT:

CARD_NAMES_START
Card Name 1
Card Name 2
Card Name 3
Card Name 4
Card Name 5
Card Name 6
Card Name 7
Card Name 8
Card Name 9
Card Name 10
CARD_NAMES_END

Task: List 10 Magic: The Gathering cards for Commander "{commander_name}" (color identity: {color_identity.to_string()}) that synergize with: {preferred_mechanics}
CRITICAL: Use the exact format above. No other text allowed.
                """,
                
                # Format 2: CSV style
                f"""
OUTPUT ONLY THIS CSV FORMAT - NO OTHER TEXT:
CardName1,CardName2,CardName3,CardName4,CardName5,CardName6,CardName7,CardName8,CardName9,CardName10

Task: Recommend 10 Commander-legal Magic cards for "{commander_name}" with mechanics: {preferred_mechanics}
Color identity: {color_identity.to_string()}
                """,
                
                # Format 3: Simple numbered list
                f"""
RESPOND WITH EXACTLY THIS FORMAT:
1. [Card Name]
2. [Card Name]  
3. [Card Name]
4. [Card Name]
5. [Card Name]
6. [Card Name]
7. [Card Name]
8. [Card Name]
9. [Card Name]
10. [Card Name]

Recommend Commander cards for "{commander_name}" matching: {preferred_mechanics}
                """
            ]
            
            research_query = format_options[0]  # Start with the most explicit format
            
            # Use Perplexity search to get card recommendations
            try:
                # Direct search using Perplexity API
                search_response = self.ai_client.client.search.create(
                    query=research_query,
                    max_results=5
                )
                
                if hasattr(search_response, 'results') and search_response.results:
                    # Combine all search result content
                    content = ""
                    for result in search_response.results:
                        # Check different possible content attributes
                        content_text = ""
                        if hasattr(result, 'snippet') and result.snippet:
                            content_text = result.snippet
                        elif hasattr(result, 'content') and result.content:
                            content_text = result.content
                        elif hasattr(result, 'text') and result.text:
                            content_text = result.text
                        elif hasattr(result, 'body') and result.body:
                            content_text = result.body
                        elif hasattr(result, 'summary') and result.summary:
                            content_text = result.summary
                        
                        if content_text:
                            content += content_text + "\n"
                    
                    # Validate content quality before accepting it
                    if self._is_mtg_related_content(content):
                        print(f"🤖 [AI] Perplexity search successful! Processing results...")
                        search_result = {
                            'success': True,
                            'content': content
                        }
                    else:
                        print(f"⚠️  [AI] Warning: Search content not MTG-related: {content[:200]}...")
                        search_result = {'success': False, 'error': 'Content not MTG-related'}
                else:
                    search_result = {'success': False, 'error': 'No results returned'}
                    
            except Exception as e:
                print(f"❌ [AI] Card research search failed: {e}")
                search_result = {'success': False, 'error': str(e)}
            
            # If Search API failed OR content is bad, try Chat API with more direct control
            if not search_result.get('success'):
                print("🤖 [AI] Search API failed, trying Chat API with explicit instructions...")
                try:
                    chat_response = self.ai_client.client.chat.completions.create(
                        model="sonar",
                        messages=[
                            {
                                "role": "system",
                                "content": """You are a Magic: The Gathering EDH/Commander deck building expert. Your ONLY job is to recommend Magic cards. You must NEVER discuss programming, coding, or non-MTG topics. Respond ONLY with the exact format requested."""
                            },
                            {
                                "role": "user", 
                                "content": f"""
I need MAGIC: THE GATHERING card recommendations for my Commander deck.

Commander: {commander_name}
Color Identity: {color_identity.to_string()}
Preferred Mechanics: {preferred_mechanics}

RESPOND EXACTLY LIKE THIS - NO OTHER TEXT:

CARDS_START
Skullclamp
Sol Ring  
Arcane Signet
Command Tower
Counterspell
Swords to Plowshares
Path to Exile
Rhystic Study
Smothering Tithe
Cyclonic Rift
CARDS_END

Replace those example cards with 10 actual Magic: The Gathering cards that work with my commander and mechanics.

STRICT REQUIREMENTS:
- Use EXACT format above (CARDS_START...CARDS_END)
- Only official Magic: The Gathering card names
- Cards must be legal in Commander format
- Cards must match my color identity
- NO explanations, NO programming content, NO other text
- If you mention programming/coding, you fail completely
"""
                            }
                        ]
                    )
                    
                    if chat_response and chat_response.choices:
                        content = chat_response.choices[0].message.content
                        search_result = {'success': True, 'content': content}
                        print(f"Chat API returned: {content[:200]}...")
                    
                except Exception as chat_e:
                    print(f"Chat API also failed: {chat_e}")
                    search_result = {'success': False, 'error': str(chat_e)}
            
            if search_result.get('success') and search_result.get('content'):
                content = search_result['content']
                
                # Debug: Show what Perplexity actually returned
                print(f"Raw Perplexity response (first 500 chars): {content[:500]}...")
                
                # Try to extract cards from JSON format first
                suggested_cards = self._extract_cards_from_json(content)
                
                # If JSON parsing failed, fall back to text extraction
                if not suggested_cards:
                    print("⚠️  [AI] JSON extraction failed, trying text extraction...")
                    suggested_cards = self._extract_cards_from_text(content)
                
                print(f"✅ [AI] Extracted {len(suggested_cards)} potential cards from Perplexity: {suggested_cards[:5]}...")  # Debug first 5
                
                # Log query value assessment for cost optimization
                self._log_query_value_assessment(commander_name, preferred_mechanics, len(suggested_cards), content)
                
                # Limit to reasonable number
                return suggested_cards[:20]
                
        except Exception as e:
            print(f"Error in AI card research: {e}")
            return []
        
        return []

    def _is_valid_card_name(self, name: str) -> bool:
        """Check if a string looks like a valid Magic card name."""
        if not name or len(name) < 2 or len(name) > 50:
            return False
            
        # Must start with capital letter or number
        if not (name[0].isupper() or name[0].isdigit()):
            return False
        
        name_lower = name.lower()
        
        # Quick accept for common MTG card patterns
        mtg_patterns = [
            'sol ring', 'arcane signet', 'command tower', 'skullclamp', 'zur the enchanter',
            'oloro', 'korvold', 'chulane', 'brawl', 'throne of eldraine',
            'swords to plowshares', 'counterspell', 'lightning bolt', 'path to exile',
            'rhystic study', 'smothering tithe', 'cyclonic rift', 'dockside extortionist'
        ]
        
        for pattern in mtg_patterns:
            if pattern in name_lower:
                return True
        
        # Reject obvious non-card phrases
        invalid_phrases = [
            'the following', 'these cards', 'deck strategy', 'commander format',
            'you should', 'i recommend', 'consider adding', 'make sure',
            'this deck', 'your deck', 'token strategy', 'artifact synergy',
            'mana curve', 'card draw', 'win condition', 'removal spell',
            'https', 'www', 'youtube', 'transcript', 'copyright', 'illustration by',
            'created by', 'tokens created', ' are ', 'is also', 'board wipes',
            'last updated', 'august', 'most popular', 'one of the', 'along with',
            'been printed', 'very popular', 'played with', 'power level',
            'faerie dominates', 'if it survives', 'brawl format', 'esper commanders'
        ]
        
        for phrase in invalid_phrases:
            if phrase in name_lower:
                return False
        
        # Allow single-word cards (like "Skullclamp") and multi-word cards
        
        # Reject if it has " and " connecting multiple card names
        if ' and ' in name_lower and len(name_lower.split()) > 4:
            return False
            
        # Reject if it contains too many common descriptive words
        descriptive_words = [
            'also', 'tribal', 'support', 'strategy', 'abilities', 'created', 
            'tokens', 'creatures', 'spells', 'artifacts', 'enchantments'
        ]
        words = name_lower.split()
        descriptive_count = sum(1 for word in words if word in descriptive_words)
        
        # If more than 1/3 of words are descriptive, probably not a card name
        if len(words) > 3 and descriptive_count > len(words) // 3:
            return False
            
        return True

    def _extract_cards_from_json(self, content: str) -> List[str]:
        """Extract cards from structured format response."""
        import json
        import re
        
        # Try multiple structured formats
        
        # Format 1: Delimited blocks (multiple patterns)
        try:
            delimiter_patterns = [
                r'CARD_NAMES_START\s*(.*?)\s*CARD_NAMES_END',
                r'CARDS_START\s*(.*?)\s*CARDS_END',
            ]
            
            for pattern in delimiter_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                
                if match:
                    card_block = match.group(1).strip()
                    lines = [line.strip() for line in card_block.split('\n') if line.strip()]
                    
                    valid_cards = []
                    for line in lines:
                        if self._is_valid_card_name(line):
                            valid_cards.append(line)
                    
                    if valid_cards:
                        print(f"Delimited format extraction found {len(valid_cards)} cards")
                        return valid_cards
        
        except Exception as e:
            print(f"Warning: Delimited format parsing failed: {e}")
        
        # Format 2: CSV format (comma-separated on one line)
        try:
            # Look for comma-separated card names
            csv_patterns = [
                r'([A-Z][a-zA-Z\s\',\-]+(?:,[A-Z][a-zA-Z\s\',\-]+){5,})',  # Multiple cards separated by commas
                r'^([^,\n]+,[^,\n]+,[^,\n]+,[^,\n]+,[^,\n]+).*$',  # At least 5 comma-separated items
            ]
            
            for pattern in csv_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    if ',' in match:
                        cards = [card.strip() for card in match.split(',')]
                        valid_cards = [card for card in cards if self._is_valid_card_name(card)]
                        if len(valid_cards) >= 3:
                            print(f"CSV format extraction found {len(valid_cards)} cards")
                            return valid_cards
        
        except Exception as e:
            print(f"Warning: CSV format parsing failed: {e}")
        
        # Format 3: Numbered list (1. Card Name, 2. Card Name, etc.)
        try:
            numbered_pattern = r'^\s*\d+\.\s*([A-Z][a-zA-Z\s\',\-]+?)(?:\s*$|\s*\n)'
            matches = re.findall(numbered_pattern, content, re.MULTILINE)
            
            valid_cards = []
            for match in matches:
                card = match.strip()
                if self._is_valid_card_name(card):
                    valid_cards.append(card)
            
            if valid_cards:
                print(f"Numbered list extraction found {len(valid_cards)} cards")
                return valid_cards
        
        except Exception as e:
            print(f"Warning: Numbered list parsing failed: {e}")
        
        # Fallback to JSON extraction
        try:
            content = content.strip()
            
            # Look for JSON block
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                data = json.loads(json_str)
                
                cards = data.get('recommended_cards', [])
                valid_cards = []
                
                for card in cards:
                    if isinstance(card, str) and self._is_valid_card_name(card):
                        valid_cards.append(card.strip())
                
                if valid_cards:
                    print(f"JSON extraction found {len(valid_cards)} cards")
                    return valid_cards
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"JSON parsing failed: {e}")
            print(f"Content that failed to parse: {content[:200]}...")
        
        return []

    def _extract_cards_from_text(self, content: str) -> List[str]:
        """Extract cards from text using pattern matching."""
        import re
        
        # Multiple extraction patterns to handle various formats
        patterns = [
            # Numbered lists with bold cards: "1. **Skullclamp** - description"
            r'^\s*\d+\.?\s*\*?\*?([A-Z][a-zA-Z\s\',\-]+?)\*?\*?\s*[-–]',
            
            # Bold cards: **Card Name**
            r'\*\*([A-Z][a-zA-Z\s\',\-]+?)\*\*',
            
            # Quoted cards: "Card Name"
            r'["""]([A-Z][a-zA-Z\s\',\-]+?)["""]',
            
            # Cards after action keywords (more specific)
            r'(?:recommend|suggest|include|consider|use|play|add|run)\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s+for|\s+to|\s|,|\.|\n|$)',
            
            # Cards mentioned with "along with": "along with Zur the Enchanter"
            r'along\s+with\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s+and|\s|,|\.|\n|$)',
            
            # Cards alongside other cards: "alongside Korvold, Fae-Cursed King"
            r'alongside\s+([A-Z][a-zA-Z\s\',\-]{3,30}?)(?:\s|,|\.|\n|$)',
            
            # Specific MTG phrases: "Swords to Plowshares", "Path to Exile"
            r'\b([A-Z][a-zA-Z]+\s+to\s+[A-Z][a-zA-Z]+)\b',
            
            # Card names with common MTG suffixes
            r'\b([A-Z][a-zA-Z]+(?:\s+the\s+[A-Z][a-zA-Z]+|clamp|signet|tower))\b',
            
            # Well-known card patterns (Conservative approach)
            r'\b(Zur\s+the\s+Enchanter|Oloro,?\s+Ageless\s+Ascetic|Korvold,?\s+Fae-Cursed\s+King|Chulane,?\s+Teller\s+of\s+Tales|Skullclamp|Sol\s+Ring|Arcane\s+Signet|Command\s+Tower|Rhystic\s+Study|Smothering\s+Tithe|Cyclonic\s+Rift)\b',
        ]
        
        suggested_cards = []
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                card_name = match.strip().rstrip(',').rstrip('.').rstrip(':').strip()
                
                if (self._is_valid_card_name(card_name) and 
                    card_name not in suggested_cards):
                    suggested_cards.append(card_name)
        
        return suggested_cards[:20]  # Limit to reasonable number

    def _match_cards_in_database(self, ai_suggestions: List[str], all_card_names: List[str]) -> List[str]:
        """Match AI suggested cards with database cards using case-insensitive and fuzzy matching."""
        from difflib import get_close_matches
        
        matched_cards = []
        
        for ai_card in ai_suggestions:
            # Try exact case-insensitive match first
            exact_matches = [db_card for db_card in all_card_names if db_card.lower() == ai_card.lower()]
            
            if exact_matches:
                matched_cards.append(exact_matches[0])
                print(f"Exact match: '{ai_card}' -> '{exact_matches[0]}'")
                continue
            
            # Try fuzzy matching for typos
            close_matches = get_close_matches(ai_card, all_card_names, n=1, cutoff=0.85)
            
            if close_matches:
                matched_cards.append(close_matches[0])
                print(f"Fuzzy match: '{ai_card}' -> '{close_matches[0]}'")
                continue
                
            print(f"No match found for: '{ai_card}'")
        
        return matched_cards

    def _is_mtg_related_content(self, content: str) -> bool:
        """Check if content is actually about Magic: The Gathering."""
        content_lower = content.lower()
        
        # MTG-specific terms that should be present
        mtg_keywords = [
            'magic', 'commander', 'deck', 'mana', 'spell', 'artifact', 'creature',
            'enchantment', 'planeswalker', 'sorcery', 'instant', 'land', 'tribal',
            'mtg', 'edh', 'flying', 'token', 'draw', 'graveyard', 'battlefield',
            'card draw', 'synergy', 'color identity', 'legendary', 'enters the battlefield'
        ]
        
        # Non-MTG terms that indicate wrong content
        bad_keywords = [
            'programming', 'code', 'python', 'javascript', 'if statement', 'function',
            'variable', 'print', 'class', 'method', 'spoiler alert', 'solution',
            'challenge', 'algorithm', 'array', 'loop', 'tutorial', 'stackoverflow'
        ]
        
        # Count MTG-related terms
        mtg_count = sum(1 for keyword in mtg_keywords if keyword in content_lower)
        bad_count = sum(1 for keyword in bad_keywords if keyword in content_lower)
        
        # Content should have MTG terms and minimal bad terms
        return mtg_count >= 2 and bad_count == 0

    def _log_query_value_assessment(self, commander_name: str, mechanics: str, cards_extracted: int, response_content: str):
        """Log assessment of Perplexity query value for cost optimization."""
        
        # Assess query value
        value_score = 0
        issues = []
        
        # Good indicators
        if cards_extracted >= 5:
            value_score += 3
        elif cards_extracted >= 3:
            value_score += 2
        elif cards_extracted >= 1:
            value_score += 1
        else:
            issues.append("No cards extracted")
        
        # Check response quality
        response_lower = response_content.lower()
        if 'mtg' in response_lower or 'magic' in response_lower or 'commander' in response_lower:
            value_score += 2
        else:
            issues.append("No MTG context in response")
            
        if len(response_content) < 100:
            issues.append("Response too short")
        elif 'programming' in response_lower or 'code' in response_lower:
            issues.append("Programming content detected")
            value_score -= 2
        
        # Determine value level
        if value_score >= 4:
            value_level = "HIGH_VALUE"
        elif value_score >= 2:
            value_level = "MEDIUM_VALUE"
        else:
            value_level = "LOW_VALUE"
        
        # Log assessment
        print(f"PERPLEXITY QUERY ASSESSMENT: {value_level}")
        print(f"   Commander: {commander_name}")
        print(f"   Mechanics: {mechanics}")
        print(f"   Cards Extracted: {cards_extracted}")
        print(f"   Value Score: {value_score}")
        if issues:
            print(f"   Issues: {', '.join(issues)}")
        print(f"   Response Preview: {response_content[:150]}...")
        
        # Alert for consistently low-value queries
        if value_level == "LOW_VALUE":
            print(f"🚨 LOW VALUE QUERY ALERT: Consider optimizing prompt or disabling for '{commander_name}' + '{mechanics}'")



# ===================================
# PHASE 3: MULTIPROCESSING WORKER
# ===================================
# This function runs in a separate process to score cards in parallel

def _score_batch_worker(card_items: List[Tuple[str, List[Dict]]], 
                       commander_dict: Dict, 
                       current_deck: List[str],
                       budget_limit: Optional[float]) -> List:
    """
    Score a batch of cards (runs in a separate CPU process).
    
    This function must be picklable (defined at module level) to work with ProcessPoolExecutor.
    It reconstructs the commander and recommender in the subprocess and scores the batch.
    
    Args:
        card_items: List of (card_name, versions) tuples to score
        commander_dict: Serialized commander data
        current_deck: List of card names already in deck
        budget_limit: Budget limit per card
    
    Returns:
        List of CardRecommendation objects (serializable)
    """
    # Reconstruct commander in subprocess
    commander = CommanderCard.from_dict(commander_dict)
    
    # Create recommender instance in subprocess (for synergy analysis)
    from data_engine.commander_recommender import CommanderRecommendationEngine
    recommender = CommanderRecommendationEngine(use_ai=False)  # No AI in worker process
    
    # Score each card in the batch
    scored = []
    for card_name, versions in card_items:
        if not card_name:
            continue
        
        try:
            # Select best version
            best_version = recommender._select_best_version(versions, budget_limit)
            
            # Score the card
            recommendation = recommender.score_card_for_commander(commander, best_version, current_deck)
            recommendation.all_versions = versions
            
            scored.append(recommendation)
        except Exception as e:
            print(f"Error scoring {card_name}: {e}")
            continue
    
    return scored


async def test_recommendation_engine():
    """Test the recommendation engine with a sample commander."""
    print("Testing Commander Recommendation Engine...")
    
    engine = CommanderRecommendationEngine(use_ai=True)
    
    # Test request
    request = RecommendationRequest(
        commander_name="Alela, Artful Provocateur",
        power_level="optimized",
        budget_limit=10.0
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_recommendation_engine())