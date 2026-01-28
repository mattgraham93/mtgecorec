"""
scoring_adapter.py - Adapter for CardScorer to Existing API

Bridges new CardScorer output to existing CommanderRecommendationEngine API format.
Ensures zero breaking changes to frontend while using new scoring backend.

Created: January 23, 2026
"""

import pandas as pd
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ScoringAdapter:
    """
    Adapter that converts new CardScorer output to existing API format.
    
    Maintains exact same CardRecommendation and DeckRecommendation structures
    so frontend sees no breaking changes.
    """
    
    def __init__(self):
        """Initialize adapter with CardScorer."""
        try:
            from data_engine.card_scoring import CardScorer
            self.scorer = CardScorer()
            logger.info("ScoringAdapter initialized with CardScorer")
        except ImportError as e:
            logger.error(f"Failed to import CardScorer: {e}")
            raise
    
    def score_to_recommendation(self,
                               card: Dict[str, Any],
                               score: float,
                               components: Dict[str, float],
                               commander: Dict[str, Any],
                               all_versions: Optional[List[Dict[str, Any]]] = None) -> 'CardRecommendation':
        """
        Convert new scoring system output → existing CardRecommendation format.
        
        CRITICAL: Maintains exact same fields frontend expects
        
        Args:
            card: Card data dict
            score: Total score from CardScorer (0-100)
            components: Component scores dict from CardScorer
            commander: Commander card data
            all_versions: List of all card printings
        
        Returns:
            CardRecommendation with all required fields
        """
        # Import here to avoid circular dependency
        from data_engine.commander_recommender import CardRecommendation
        
        # Map total_score (0-100) to confidence_score (0.0-1.0)
        confidence_score = min(score / 100.0, 1.0)
        
        # Build human-readable reasons from component scores
        reasons = self._build_reasons(components, commander)
        
        # Determine category (existing logic)
        category = self._determine_category(card, components)
        
        # Preserve existing CardRecommendation structure
        return CardRecommendation(
            card_name=card.get('name', ''),
            card_data=card,
            confidence_score=confidence_score,  # Frontend expects 0.0-1.0
            synergy_score=min(components['mechanic_synergy'] / 100.0, 1.0),  # Convert to 0.0-1.0
            reasons=reasons,  # Frontend displays these
            category=category,  # Frontend groups by this
            estimated_price=card.get('prices', {}).get('usd') if isinstance(card.get('prices'), dict) else None,
            all_versions=all_versions,
            ai_suggested=False  # Can be overridden if from AI
        )
    
    def _build_reasons(self, components: Dict[str, float], commander: Dict[str, Any]) -> List[str]:
        """
        Generate human-readable reasons from component scores.
        Frontend displays these to users.
        
        Args:
            components: Component scores from CardScorer
            commander: Commander card data
        
        Returns:
            List of human-readable explanation strings
        """
        reasons = []
        
        # Mechanic synergy explanation (most important)
        mech_score = components.get('mechanic_synergy', 50)
        if mech_score >= 80:
            commander_name = commander.get('name', 'commander')
            reasons.append(f"Excellent mechanic synergy with {commander_name}")
        elif mech_score >= 60:
            reasons.append("Strong mechanic overlap with commander")
        elif mech_score >= 40:
            reasons.append("Good mechanic synergy")
        
        # Archetype fit
        arch_score = components.get('archetype_fit', 50)
        if arch_score >= 70:
            reasons.append("Perfect archetype match")
        elif arch_score >= 50:
            reasons.append("Fits deck strategy well")
        
        # Combo potential
        combo_score = components.get('combo_bonus', 0)
        if combo_score >= 50:
            reasons.append("Enables infinite combo potential")
        elif combo_score >= 30:
            reasons.append("Known combo piece")
        
        # Base power
        base_power = components.get('base_power', 50)
        if base_power >= 70:
            reasons.append("High-quality card")
        
        # Color identity
        color_mult = components.get('color_multiplier', 1.0)
        if color_mult == 1.0:
            reasons.append("Perfect color match")
        
        # Curve fit (if strongly needed)
        curve_fit = components.get('curve_fit', 50)
        if curve_fit >= 80:
            reasons.append("Fills important mana slot")
        
        # Type balance
        type_bal = components.get('type_balance', 50)
        if type_bal >= 75:
            reasons.append("Balances deck type distribution")
        
        return reasons
    
    def _determine_category(self, card: Dict[str, Any], components: Dict[str, float]) -> str:
        """
        Categorize card for frontend display.
        
        MUST match existing categories: 'ramp', 'removal', 'draw', 'synergy', 'combo', 'finisher'
        
        Args:
            card: Card data
            components: Component scores
        
        Returns:
            Category string that frontend expects
        """
        oracle_text = str(card.get('oracle_text', '')).lower()
        type_line = str(card.get('type_line', '')).lower()
        cmc = float(card.get('cmc', 0))
        
        # Check for land (always ramp)
        if 'land' in type_line:
            return 'ramp'
        
        # Check for mana acceleration
        mana_keywords = ['search your library for a land', 'add mana', 'sol ring', 'mana acceleration']
        if any(keyword in oracle_text for keyword in mana_keywords):
            return 'ramp'
        
        # Check for removal/interaction
        removal_keywords = ['destroy target', 'exile target', 'counter target spell', 'return target',
                          'discard', 'bounce', 'sacrifice target', 'remove target from the game']
        if any(keyword in oracle_text for keyword in removal_keywords):
            return 'removal'
        
        # Check for draw/card advantage
        draw_keywords = ['draw cards', 'draw a card', 'card advantage', 'fetch']
        if any(keyword in oracle_text for keyword in draw_keywords):
            return 'draw'
        
        # Check for combo potential
        if components.get('combo_bonus', 0) >= 30:
            return 'combo'
        
        # Check for finisher
        if cmc >= 6 or 'win the game' in oracle_text or 'infinite' in oracle_text:
            return 'finisher'
        
        # Default: high synergy
        if components.get('mechanic_synergy', 0) >= 70:
            return 'synergy'
        
        # Ultimate default
        return 'synergy'
    
    def score_all_cards_for_commander(self,
                                     commander: Dict[str, Any],
                                     current_deck: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:
        """
        Score all cards for a commander using new CardScorer.
        
        Args:
            commander: Commander card data
            current_deck: Cards already in deck
        
        Returns:
            DataFrame of scores sorted by total_score
        """
        logger.info(f"Scoring all cards for {commander.get('name', 'Unknown')}")
        
        # Use CardScorer to score all cards
        scored_results = self.scorer.score_all_cards(commander, current_deck)
        
        logger.info(f"Scoring complete: {len(scored_results)} cards scored")
        return scored_results
    
    async def generate_recommendations_compatible(self,
                                                  request: 'RecommendationRequest',
                                                  commander_repo,
                                                  card_repo) -> 'DeckRecommendation':
        """
        Drop-in replacement for CommanderRecommendationEngine.generate_recommendations().
        
        SAME SIGNATURE as existing method - Frontend won't notice the change.
        
        Args:
            request: RecommendationRequest with commander name, deck, etc.
            commander_repo: Repository/DB accessor for commander cards
            card_repo: Repository/DB accessor for all cards
        
        Returns:
            DeckRecommendation with same structure as before
        """
        from data_engine.commander_recommender import DeckRecommendation
        
        logger.info(f"Generating recommendations for {request.commander_name}")
        
        # Find commander
        commander = await commander_repo.find_by_name(request.commander_name)
        if not commander:
            raise ValueError(f"Commander not found: {request.commander_name}")
        
        commander_dict = commander.to_dict() if hasattr(commander, 'to_dict') else commander
        
        # Convert current deck strings to card dicts
        current_deck_dicts = []
        if request.current_deck:
            for card_name in request.current_deck:
                card = await card_repo.find_by_name(card_name)
                if card:
                    current_deck_dicts.append(
                        card.to_dict() if hasattr(card, 'to_dict') else card
                    )
        
        # Score all cards
        scored_results = self.score_all_cards_for_commander(commander_dict, current_deck_dicts)
        
        # Convert to CardRecommendation objects (top 99 cards)
        recommendations = []
        for _, row in scored_results.head(99).iterrows():
            card_name = row['card_name']
            
            # Fetch full card data
            card = await card_repo.find_by_name(card_name)
            if not card:
                continue
            
            card_dict = card.to_dict() if hasattr(card, 'to_dict') else card
            
            # Extract component scores
            components = {
                'base_power': row.get('base_power', 50),
                'mechanic_synergy': row.get('mechanic_synergy', 50),
                'archetype_fit': row.get('archetype_fit', 50),
                'combo_bonus': row.get('combo_bonus', 0),
                'curve_fit': row.get('curve_fit', 50),
                'type_balance': row.get('type_balance', 50),
                'color_multiplier': row.get('color_multiplier', 1.0)
            }
            
            # Convert to CardRecommendation
            rec = self.score_to_recommendation(
                card_dict,
                row['total_score'],
                components,
                commander_dict
            )
            recommendations.append(rec)
        
        # Generate mana base (placeholder - can be enhanced)
        mana_base = self._generate_default_mana_base(commander_dict)
        
        # Calculate estimated cost
        estimated_cost = self._calculate_total_cost(recommendations)
        
        # Return EXACT same structure frontend expects
        return DeckRecommendation(
            commander=commander,
            recommendations=recommendations,
            ai_analysis=None,
            mana_base_suggestions=mana_base,
            deck_strategy=f"Optimized deck for {commander_dict.get('name', 'Unknown')}",
            power_level_assessment=self._assess_power_level(recommendations),
            estimated_total_cost=estimated_cost
        )
    
    def _generate_default_mana_base(self, commander: Dict[str, Any]) -> List['CardRecommendation']:
        """
        Generate default mana base recommendations.
        
        Args:
            commander: Commander card data
        
        Returns:
            List of land recommendations (simplified)
        """
        # Placeholder: return empty list (existing code can be integrated later)
        return []
    
    def _calculate_total_cost(self, recommendations: List) -> Optional[float]:
        """
        Calculate estimated deck cost.
        
        Args:
            recommendations: List of CardRecommendation objects
        
        Returns:
            Total estimated cost or None
        """
        total = 0
        count = 0
        
        for rec in recommendations:
            if rec.estimated_price:
                try:
                    total += float(rec.estimated_price)
                    count += 1
                except (ValueError, TypeError):
                    pass
        
        return total if count > 0 else None
    
    def _assess_power_level(self, recommendations: List) -> str:
        """
        Assess deck power level from card recommendations.
        
        Args:
            recommendations: List of CardRecommendation objects
        
        Returns:
            Power level string: 'casual', 'competitive', 'cEDH'
        """
        if not recommendations:
            return 'casual'
        
        avg_confidence = sum(r.confidence_score for r in recommendations) / len(recommendations)
        
        if avg_confidence >= 0.8:
            return 'cEDH'
        elif avg_confidence >= 0.6:
            return 'competitive'
        else:
            return 'casual'
